from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.test import TestCase

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
