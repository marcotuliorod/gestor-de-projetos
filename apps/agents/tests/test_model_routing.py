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
