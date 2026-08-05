from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.agents import agent_client
from apps.agents.models import TaskRunStep
from apps.projects.models import Project


def _fake_project(**overrides):
    p = Project(name="teste", test_command="pytest", lint_command="ruff check .")
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


class BuildPromptTests(SimpleTestCase):
    def test_discuss_includes_instruction(self):
        prompt = agent_client._build_prompt(TaskRunStep.Phase.DISCUSS, _fake_project(), "faz algo", {})
        self.assertIn("faz algo", prompt)
        self.assertIn("Discuss", prompt)

    def test_plan_includes_discuss_summary(self):
        prompt = agent_client._build_prompt(
            TaskRunStep.Phase.PLAN, _fake_project(), "faz algo", {"discuss_summary": "entendi tudo"}
        )
        self.assertIn("entendi tudo", prompt)

    def test_verify_includes_project_commands(self):
        prompt = agent_client._build_prompt(TaskRunStep.Phase.VERIFY, _fake_project(), "faz algo", {})
        self.assertIn("pytest", prompt)
        self.assertIn("ruff check .", prompt)


@override_settings(AGENTS_FAKE_MODE=False)
class RunPhaseRealSafetySettingsTests(SimpleTestCase):
    """Trava as opções de segurança confirmadas por teste real contra a API
    (ver notas em agent_client.py): sandbox ligado e modelo mapeado para um
    ID real, não um alias adivinhado. Regressão aqui reabriria o
    `cat /app/.env` que o teste real mostrou funcionar sem essas opções."""

    def test_sandbox_and_model_options_are_set(self):
        captured = {}

        async def fake_query(*, prompt, options=None, transport=None):
            captured["options"] = options
            return
            yield  # pragma: no cover - make this an async generator

        with patch("claude_agent_sdk.query", fake_query):
            agent_client.run_phase(
                phase=TaskRunStep.Phase.EXECUTE,
                model="sonnet",
                project=_fake_project(),
                instruction="faz algo",
                worktree_path="/tmp/whatever",
                context={},
            )

        options = captured["options"]
        self.assertEqual(options.permission_mode, "bypassPermissions")
        self.assertTrue(options.sandbox.get("enabled"))
        self.assertTrue(options.sandbox.get("enableWeakerNestedSandbox"))
        self.assertEqual(options.model, agent_client.MODEL_IDS["sonnet"])
        self.assertEqual(options.cwd, "/tmp/whatever")


@override_settings(AGENTS_FAKE_MODE=False)
class RunPhaseRealTests(SimpleTestCase):
    def test_successful_result_maps_to_ok_phase_result(self):
        from claude_agent_sdk import ResultMessage

        fake_result = ResultMessage(
            subtype="success",
            duration_ms=100,
            duration_api_ms=90,
            is_error=False,
            num_turns=2,
            session_id="session-1",
            result="Fiz a alteração pedida.",
        )

        async def fake_query(*, prompt, options=None, transport=None):
            yield fake_result

        with patch("claude_agent_sdk.query", fake_query):
            result = agent_client.run_phase(
                phase=TaskRunStep.Phase.EXECUTE,
                model="sonnet",
                project=_fake_project(),
                instruction="faz algo",
                worktree_path="/tmp/whatever",
                context={},
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.detail, "Fiz a alteração pedida.")
        self.assertEqual(result.context_updates["execute_summary"], "Fiz a alteração pedida.")

    def test_is_error_result_maps_to_failed_phase_result(self):
        from claude_agent_sdk import ResultMessage

        fake_result = ResultMessage(
            subtype="error",
            duration_ms=100,
            duration_api_ms=90,
            is_error=True,
            num_turns=1,
            session_id="session-2",
            result="Não consegui rodar os testes.",
        )

        async def fake_query(*, prompt, options=None, transport=None):
            yield fake_result

        with patch("claude_agent_sdk.query", fake_query):
            result = agent_client.run_phase(
                phase=TaskRunStep.Phase.VERIFY,
                model="haiku",
                project=_fake_project(),
                instruction="faz algo",
                worktree_path="/tmp/whatever",
                context={},
            )

        self.assertFalse(result.ok)
        self.assertEqual(result.detail, "Não consegui rodar os testes.")

    def test_sdk_error_is_caught_gracefully(self):
        from claude_agent_sdk import CLINotFoundError

        async def fake_query(*, prompt, options=None, transport=None):
            raise CLINotFoundError()
            yield  # pragma: no cover - make this an async generator

        with patch("claude_agent_sdk.query", fake_query):
            result = agent_client.run_phase(
                phase=TaskRunStep.Phase.DISCUSS,
                model="haiku",
                project=_fake_project(),
                instruction="faz algo",
                worktree_path="/tmp/whatever",
                context={},
            )

        self.assertFalse(result.ok)
        self.assertIn("Erro do Agent SDK", result.detail)
