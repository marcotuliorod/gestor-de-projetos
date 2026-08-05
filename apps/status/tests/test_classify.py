from django.test import SimpleTestCase

from apps.status.classify import classify_state
from apps.status.models import ProjectState


class ClassifyStateTests(SimpleTestCase):
    def test_ci_failure_wins(self):
        state, summary = classify_state({"ci_status": "failure", "open_prs": 2, "branch": "main"})
        self.assertEqual(state, ProjectState.PRECISA_DE_VOCE)
        self.assertIn("main", summary)

    def test_ci_error_also_wins(self):
        state, _ = classify_state({"ci_status": "error", "open_prs": 0})
        self.assertEqual(state, ProjectState.PRECISA_DE_VOCE)

    def test_open_pr_without_ci_failure(self):
        state, summary = classify_state({"ci_status": "success", "open_prs": 1, "ahead": 3, "behind": 0})
        self.assertEqual(state, ProjectState.EM_DIA)
        self.assertIn("1 PR", summary)

    def test_no_prs_no_failure(self):
        state, _ = classify_state({"ci_status": "", "open_prs": 0})
        self.assertEqual(state, ProjectState.PARADO)

    def test_missing_keys_default_safely(self):
        state, _ = classify_state({})
        self.assertEqual(state, ProjectState.PARADO)
