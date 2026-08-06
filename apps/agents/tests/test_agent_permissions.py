from django.test import TestCase

from apps.agents.agent_client import disallowed_tools_for
from apps.projects.models import Project


class DisallowedToolsTests(TestCase):
    """RF-03: as permissões editadas na tela precisam mudar de verdade o
    que o agente pode fazer — antes disso `agent_permissions` era um campo
    que nada lia."""

    def _project(self, permissions):
        return Project.objects.create(name="teste", agent_permissions=permissions)

    def test_empty_permissions_block_nothing(self):
        """Projetos cadastrados antes da tela existir têm o campo vazio e
        não podem mudar de comportamento em silêncio."""
        self.assertEqual(disallowed_tools_for(self._project({})), [])

    def test_blocking_bash(self):
        self.assertEqual(disallowed_tools_for(self._project({"allow_bash": False})), ["Bash"])

    def test_blocking_web_covers_both_tools(self):
        blocked = disallowed_tools_for(self._project({"allow_web": False}))
        self.assertEqual(sorted(blocked), ["WebFetch", "WebSearch"])

    def test_blocking_everything(self):
        blocked = disallowed_tools_for(self._project({"allow_bash": False, "allow_web": False}))
        self.assertEqual(sorted(blocked), ["Bash", "WebFetch", "WebSearch"])

    def test_explicitly_allowing_blocks_nothing(self):
        self.assertEqual(disallowed_tools_for(self._project({"allow_bash": True, "allow_web": True})), [])

    def test_null_permissions_do_not_raise(self):
        project = Project.objects.create(name="sem-permissoes")
        project.agent_permissions = None
        self.assertEqual(disallowed_tools_for(project), [])
