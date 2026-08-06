from django.test import TestCase

from apps.agents.model_routing import choose_model
from apps.agents.models import TaskRunStep
from apps.projects.models import Project

Phase = TaskRunStep.Phase


class ChooseModelTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="teste", default_model=Project.Model.AUTO)

    def test_auto_mode_uses_table_defaults(self):
        self.assertEqual(choose_model(self.project, Phase.DISCUSS, 0), Project.Model.HAIKU)
        self.assertEqual(choose_model(self.project, Phase.PLAN, 0), Project.Model.SONNET)
        self.assertEqual(choose_model(self.project, Phase.EXECUTE, 0), Project.Model.SONNET)
        self.assertEqual(choose_model(self.project, Phase.VERIFY, 0), Project.Model.HAIKU)
        self.assertEqual(choose_model(self.project, Phase.SHIP, 0), Project.Model.HAIKU)

    def test_manual_override_always_wins(self):
        self.project.default_model = Project.Model.HAIKU
        self.project.save()
        # Mesmo com muitas falhas de Verify, o override manual não escala.
        self.assertEqual(choose_model(self.project, Phase.EXECUTE, 5), Project.Model.HAIKU)
        self.assertEqual(choose_model(self.project, Phase.PLAN, 5), Project.Model.HAIKU)

    def test_escalates_to_opus_after_threshold(self):
        self.assertEqual(choose_model(self.project, Phase.EXECUTE, 1), Project.Model.SONNET)
        self.assertEqual(choose_model(self.project, Phase.EXECUTE, 2), Project.Model.OPUS)
        self.assertEqual(choose_model(self.project, Phase.PLAN, 2), Project.Model.OPUS)

    def test_verify_and_ship_never_escalate(self):
        self.assertEqual(choose_model(self.project, Phase.VERIFY, 5), Project.Model.HAIKU)
        self.assertEqual(choose_model(self.project, Phase.SHIP, 5), Project.Model.HAIKU)

    def test_discuss_never_escalates(self):
        self.assertEqual(choose_model(self.project, Phase.DISCUSS, 5), Project.Model.HAIKU)


class ModelOverrideTests(TestCase):
    """RF-19: o override escolhido no Composer vale para aquela tarefa e
    tem precedência sobre o padrão do projeto."""

    def setUp(self):
        self.auto = Project.objects.create(name="auto", default_model=Project.Model.AUTO)
        self.fixo = Project.objects.create(name="fixo", default_model=Project.Model.HAIKU)

    def test_task_override_wins_over_automatic(self):
        model = choose_model(self.auto, Phase.DISCUSS, 0, model_override="opus")
        self.assertEqual(model, "opus")

    def test_task_override_wins_over_project_default(self):
        """A escolha é para *esta* tarefa — mais específica que o padrão."""
        model = choose_model(self.fixo, Phase.EXECUTE, 0, model_override="opus")
        self.assertEqual(model, "opus")

    def test_empty_override_falls_back_to_project_default(self):
        self.assertEqual(choose_model(self.fixo, Phase.EXECUTE, 0, model_override=""), "haiku")

    def test_auto_override_is_treated_as_no_override(self):
        model = choose_model(self.auto, Phase.EXECUTE, 0, model_override=Project.Model.AUTO)
        self.assertEqual(model, Project.Model.SONNET)

    def test_override_does_not_escalate_on_verify_failures(self):
        """Se alguém fixou Haiku, não trocamos por Opus às escondidas."""
        model = choose_model(self.auto, Phase.EXECUTE, 5, model_override="haiku")
        self.assertEqual(model, "haiku")

    def test_automatic_still_escalates(self):
        model = choose_model(self.auto, Phase.EXECUTE, 2, model_override="")
        self.assertEqual(model, Project.Model.OPUS)
