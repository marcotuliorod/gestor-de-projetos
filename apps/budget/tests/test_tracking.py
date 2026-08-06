from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.agents.models import TaskRun, TaskRunStep
from apps.budget import tracking
from apps.budget.models import BudgetSettings
from apps.projects.models import Project


def _make_step(project, cost_usd, created_at):
    task_run = TaskRun.objects.create(project=project, instruction="x")
    step = TaskRunStep.objects.create(
        task_run=task_run, phase=TaskRunStep.Phase.EXECUTE, status=TaskRunStep.Status.DONE, cost_usd=cost_usd
    )
    TaskRunStep.objects.filter(pk=step.pk).update(created_at=created_at)
    return step


class CurrentWindowBoundsTests(TestCase):
    def test_landed_mid_week(self):
        settings_obj = BudgetSettings(reset_weekday=1, reset_hour=9)  # terça 09:00
        now = datetime(2026, 1, 7, 15, 0, tzinfo=dt_timezone.utc)  # quarta
        start, end = tracking.current_window_bounds(now=now, settings_obj=settings_obj)
        self.assertEqual(start, datetime(2026, 1, 6, 9, 0, tzinfo=dt_timezone.utc))  # terça anterior
        self.assertEqual(end, datetime(2026, 1, 13, 9, 0, tzinfo=dt_timezone.utc))

    def test_before_reset_hour_on_reset_day_uses_previous_week(self):
        settings_obj = BudgetSettings(reset_weekday=1, reset_hour=9)
        now = datetime(2026, 1, 6, 8, 0, tzinfo=dt_timezone.utc)  # terça, antes das 9h
        start, _ = tracking.current_window_bounds(now=now, settings_obj=settings_obj)
        self.assertEqual(start, datetime(2025, 12, 30, 9, 0, tzinfo=dt_timezone.utc))


class UsageTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="p1")
        self.other_project = Project.objects.create(name="p2")

    def test_usage_usd_sums_within_range_only(self):
        start = datetime(2026, 1, 6, 9, 0, tzinfo=dt_timezone.utc)
        end = datetime(2026, 1, 13, 9, 0, tzinfo=dt_timezone.utc)
        _make_step(self.project, Decimal("1.50"), datetime(2026, 1, 6, 10, 0, tzinfo=dt_timezone.utc))
        _make_step(self.project, Decimal("2.00"), datetime(2026, 1, 12, 23, 0, tzinfo=dt_timezone.utc))
        _make_step(self.project, Decimal("99.00"), datetime(2026, 1, 5, 0, 0, tzinfo=dt_timezone.utc))  # fora

        total = tracking.usage_usd(start, end)
        self.assertEqual(total, Decimal("3.50"))

    def test_usage_ignores_null_cost(self):
        start = datetime(2026, 1, 6, 9, 0, tzinfo=dt_timezone.utc)
        end = datetime(2026, 1, 13, 9, 0, tzinfo=dt_timezone.utc)
        _make_step(self.project, None, datetime(2026, 1, 6, 10, 0, tzinfo=dt_timezone.utc))
        total = tracking.usage_usd(start, end)
        self.assertEqual(total, Decimal("0"))

    def test_usage_by_project_groups_correctly(self):
        start = datetime(2026, 1, 6, 9, 0, tzinfo=dt_timezone.utc)
        end = datetime(2026, 1, 13, 9, 0, tzinfo=dt_timezone.utc)
        _make_step(self.project, Decimal("1.00"), datetime(2026, 1, 6, 10, 0, tzinfo=dt_timezone.utc))
        _make_step(self.other_project, Decimal("5.00"), datetime(2026, 1, 6, 10, 0, tzinfo=dt_timezone.utc))

        by_project = tracking.usage_by_project(start, end)
        self.assertEqual(by_project[self.project.id], Decimal("1.00"))
        self.assertEqual(by_project[self.other_project.id], Decimal("5.00"))


class BudgetStateTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="p1")

    def test_state_below_warning_is_normal(self):
        settings_obj = BudgetSettings.load()
        settings_obj.quota_total_usd = Decimal("100")
        settings_obj.pause_threshold_pct = 85
        settings_obj.save()
        start, _ = tracking.current_window_bounds()
        _make_step(self.project, Decimal("10.00"), start)

        state = tracking.budget_state()
        self.assertEqual(state["color"], "normal")
        self.assertFalse(state["should_pause_nightly"])
        self.assertFalse(state["warn"])

    def test_state_above_threshold_is_critico_and_pauses(self):
        settings_obj = BudgetSettings.load()
        settings_obj.quota_total_usd = Decimal("100")
        settings_obj.pause_threshold_pct = 85
        settings_obj.save()
        start, _ = tracking.current_window_bounds()
        _make_step(self.project, Decimal("90.00"), start)

        state = tracking.budget_state()
        self.assertEqual(state["color"], "critico")
        self.assertTrue(state["should_pause_nightly"])
        self.assertTrue(state["warn"])

    def test_zero_quota_never_pauses(self):
        settings_obj = BudgetSettings.load()
        settings_obj.quota_total_usd = Decimal("0")
        settings_obj.save()
        state = tracking.budget_state()
        self.assertEqual(state["pct"], 0)
        self.assertFalse(state["should_pause_nightly"])

    def test_weekly_history_returns_n_entries_oldest_first(self):
        weeks = tracking.weekly_history(n=6)
        self.assertEqual(len(weeks), 6)
        starts = [w["week_start"] for w in weeks]
        self.assertEqual(starts, sorted(starts))


class ProjectionTests(SimpleTestCase):
    """RF-11: projeção de esgotamento. As frases vêm do design de
    referência (`design/Gestor de Projetos.dc.html`)."""

    def setUp(self):
        self.start = datetime(2026, 8, 3, 9, 0, tzinfo=dt_timezone.utc)  # segunda 09:00
        self.end = self.start + timedelta(days=7)

    def _projection(self, used, quota, hours_elapsed, reserve_pct=0):
        now = self.start + timedelta(hours=hours_elapsed)
        return tracking.projection(
            Decimal(str(used)), Decimal(str(quota)), self.start, self.end, now=now, reserve_pct=reserve_pct
        )

    def test_slow_burn_lasts_past_the_reset(self):
        # $1 em 24h de uma janela de 7 dias, cota $100: sobra de longe.
        self.assertEqual(self._projection(1, 100, 24), "No ritmo atual, sobra cota até o reset.")

    def test_fast_burn_names_when_it_runs_out(self):
        # Metade da cota em um dia — acaba por volta do terceiro dia.
        text = self._projection(50, 100, 24)
        self.assertTrue(text.startswith("No ritmo atual, a cota acaba "), text)

    def test_reserve_band_reports_what_is_left(self):
        text = self._projection(92, 100, 48, reserve_pct=15)
        self.assertEqual(text, "Restam 8% antes da reserva pessoal.")

    def test_no_quota_configured_says_nothing(self):
        """Cota zero é o padrão do sistema — projetar sobre ela seria dividir
        por zero e inventar um número."""
        self.assertEqual(self._projection(10, 0, 24), "")

    def test_no_usage_says_nothing(self):
        self.assertEqual(self._projection(0, 100, 24), "")

    def test_fresh_window_says_nothing(self):
        """Extrapolar os primeiros minutos de uma janela de 7 dias produziria
        uma previsão absurda a partir de uma amostra minúscula."""
        self.assertEqual(self._projection(5, 100, 0.2), "")

    def test_exhausted_quota_is_stated_plainly(self):
        self.assertEqual(self._projection(120, 100, 48), "A cota semanal já foi consumida por inteiro.")

    def test_period_of_day_wording(self):
        self.assertEqual(tracking._period_of_day(3), "de madrugada")
        self.assertEqual(tracking._period_of_day(9), "de manhã")
        self.assertEqual(tracking._period_of_day(15), "à tarde")
        self.assertEqual(tracking._period_of_day(21), "à noite")


class CacheTokensTests(TestCase):
    """RF-22: a economia de cache precisa ser visível para o requisito ser
    verificável, e não apenas alegado."""

    def setUp(self):
        self.project = Project.objects.create(name="p")
        self.task_run = TaskRun.objects.create(project=self.project, instruction="x")
        self.start = datetime(2026, 8, 3, 9, 0, tzinfo=dt_timezone.utc)
        self.end = self.start + timedelta(days=7)

    def _step(self, read, written, when=None):
        step = TaskRunStep.objects.create(
            task_run=self.task_run,
            phase=TaskRunStep.Phase.EXECUTE,
            cache_read_tokens=read,
            cache_write_tokens=written,
        )
        TaskRunStep.objects.filter(pk=step.pk).update(created_at=when or (self.start + timedelta(hours=2)))
        return step

    def test_sums_within_the_window(self):
        self._step(1000, 200)
        self._step(500, 100)
        self.assertEqual(tracking.cache_tokens(self.start, self.end), {"read": 1500, "written": 300})

    def test_ignores_steps_outside_the_window(self):
        self._step(1000, 200)
        self._step(9999, 9999, when=self.start - timedelta(days=1))
        self.assertEqual(tracking.cache_tokens(self.start, self.end)["read"], 1000)

    def test_no_steps_is_zero_not_none(self):
        self.assertEqual(tracking.cache_tokens(self.start, self.end), {"read": 0, "written": 0})
