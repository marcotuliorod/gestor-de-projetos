from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from apps.status.github_client import _extract_coverage, collect_repo_status


def _run(name="test", conclusion="success", status="completed", title=None, summary=None):
    output = SimpleNamespace(title=title, summary=summary) if (title or summary) else None
    return SimpleNamespace(name=name, conclusion=conclusion, status=status, output=output)


class ExtractCoverageTests(SimpleTestCase):
    def test_percent_after_the_word(self):
        self.assertEqual(_extract_coverage([_run(title="Coverage: 84.2%")]), 84.2)

    def test_percent_before_the_word(self):
        self.assertEqual(_extract_coverage([_run(summary="93% of statements covered")]), 93.0)

    def test_portuguese_wording(self):
        self.assertEqual(_extract_coverage([_run(title="Cobertura total: 71%")]), 71.0)

    def test_comma_decimal(self):
        self.assertEqual(_extract_coverage([_run(title="Coverage 66,5%")]), 66.5)

    def test_ignores_unrelated_percentages(self):
        """Um resumo de CI é cheio de número solto — pegar qualquer '%'
        entregaria um valor errado com cara de certo."""
        self.assertIsNone(_extract_coverage([_run(summary="Build 100% complete, 3 warnings")]))

    def test_ignores_out_of_range_values(self):
        self.assertIsNone(_extract_coverage([_run(title="coverage grew 420%")]))

    def test_no_output_at_all(self):
        """Caso real dos repositórios do usuário hoje: os check-runs do
        GitHub Actions vêm com output vazio."""
        self.assertIsNone(_extract_coverage([_run(), _run(name="frontend")]))

    def test_first_run_that_reports_wins(self):
        runs = [_run(name="build"), _run(name="cov", summary="Total coverage: 55%")]
        self.assertEqual(_extract_coverage(runs), 55.0)


class CollectRepoStatusTests(SimpleTestCase):
    def _github(self, check_runs, combined_state="success", status_count=1):
        gh = MagicMock()
        repo = gh.get_repo.return_value
        repo.default_branch = "main"
        commit = repo.get_branch.return_value.commit
        commit.sha = "abc1234def"
        commit.commit.message = "corrige o cálculo\n\ndetalhes"
        commit.get_check_runs.return_value = check_runs
        commit.get_combined_status.return_value = SimpleNamespace(
            state=combined_state, total_count=status_count
        )
        repo.get_pulls.return_value = []
        return gh

    def test_reports_each_check(self):
        gh = self._github([_run(name="backend", conclusion="failure"), _run(name="frontend")])

        result = collect_repo_status(gh, "ju", "projeto")

        self.assertEqual(
            result["checks"],
            [
                {"name": "backend", "conclusion": "failure", "status": "completed"},
                {"name": "frontend", "conclusion": "success", "status": "completed"},
            ],
        )

    def test_coverage_is_none_when_ci_does_not_publish_it(self):
        gh = self._github([_run(name="backend")])
        self.assertIsNone(collect_repo_status(gh, "ju", "projeto")["coverage_pct"])

    def test_coverage_comes_through_when_published(self):
        gh = self._github([_run(name="tests", summary="Coverage: 88%")])
        self.assertEqual(collect_repo_status(gh, "ju", "projeto")["coverage_pct"], 88.0)

    def test_ci_status_falls_back_to_check_runs(self):
        """Regressão: os check-runs passaram a ser buscados sempre, não só
        quando o status combinado vem vazio — o fallback tem que continuar
        funcionando igual."""
        gh = self._github([_run(name="backend", conclusion="failure")], combined_state="")

        self.assertEqual(collect_repo_status(gh, "ju", "projeto")["ci_status"], "failure")

    def test_combined_status_wins_when_there_are_real_statuses(self):
        gh = self._github([_run(name="backend")], combined_state="pending", status_count=2)
        self.assertEqual(collect_repo_status(gh, "ju", "projeto")["ci_status"], "pending")

    def test_empty_combined_status_does_not_mask_green_checks(self):
        """Bug real, visto no próprio repositório: a API devolve
        state='pending' com total_count=0 para commits sem nenhum commit
        status — e projetos que só usam GitHub Actions nunca têm nenhum.
        Sem olhar total_count, um CI totalmente verde aparecia pendente."""
        gh = self._github(
            [_run(name="backend"), _run(name="frontend")],
            combined_state="pending",
            status_count=0,
        )

        self.assertEqual(collect_repo_status(gh, "ju", "projeto")["ci_status"], "success")

    def test_timed_out_check_counts_as_failure(self):
        gh = self._github([_run(name="e2e", conclusion="timed_out")], combined_state="", status_count=0)
        self.assertEqual(collect_repo_status(gh, "ju", "projeto")["ci_status"], "failure")

    def test_last_commit_keeps_only_the_first_message_line(self):
        gh = self._github([])
        self.assertEqual(collect_repo_status(gh, "ju", "projeto")["last_commit"], "abc1234 corrige o cálculo")
