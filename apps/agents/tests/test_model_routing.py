from django.test import SimpleTestCase, TestCase

from apps.agents.model_routing import (
    COMPLEX,
    LONG_INSTRUCTION_CHARS,
    MEDIUM,
    SIMPLE,
    choose_model,
    instruction_complexity,
)
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


class InstructionComplexityTests(SimpleTestCase):
    """RF-18: a complexidade sai da instrução, com os sinais que o próprio
    PRD sugere (decisão arquitetural explícita + arquivos citados)."""

    def test_architectural_wording_is_complex(self):
        self.assertEqual(
            instruction_complexity("Refatorar a arquitetura de autenticação para desacoplar o provedor"),
            COMPLEX,
        )

    def test_trivial_wording_is_simple(self):
        self.assertEqual(instruction_complexity("Corrigir um typo no README"), SIMPLE)

    def test_ordinary_request_is_medium(self):
        self.assertEqual(instruction_complexity("Adicionar validação de e-mail no cadastro"), MEDIUM)

    def test_many_files_plus_length_reaches_complex(self):
        instrucao = (
            "Atualizar o fluxo de cobrança tocando em src/billing/charge.py, "
            "src/billing/invoice.py e src/api/webhooks.py, mantendo compatibilidade "
            "com os contratos existentes e cobrindo com testes cada caminho de erro "
            "que hoje não tem cobertura nenhuma, incluindo os casos de retentativa "
            "e de pagamento parcial que aparecem em produção."
        )
        self.assertEqual(instruction_complexity(instrucao), COMPLEX)

    def test_trivial_wording_beats_a_single_long_paragraph(self):
        """Um pedido verboso de trocar um comentário continua sendo simples."""
        instrucao = "Corrigir um typo no comentário do módulo. " + ("detalhe irrelevante. " * 30)
        self.assertEqual(instruction_complexity(instrucao), SIMPLE)

    def test_empty_instruction_is_medium(self):
        self.assertEqual(instruction_complexity(""), MEDIUM)
        self.assertEqual(instruction_complexity("   "), MEDIUM)


class ComplexityRoutingTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="auto", default_model=Project.Model.AUTO)

    def test_complex_instruction_lifts_plan_to_opus(self):
        model = choose_model(self.project, Phase.PLAN, 0, instruction="Refatorar a arquitetura do módulo")
        self.assertEqual(model, Project.Model.OPUS)

    def test_simple_instruction_drops_execute_to_haiku(self):
        model = choose_model(self.project, Phase.EXECUTE, 0, instruction="Corrigir um typo")
        self.assertEqual(model, Project.Model.HAIKU)

    def test_medium_instruction_keeps_the_phase_default(self):
        model = choose_model(self.project, Phase.EXECUTE, 0, instruction="Adicionar um endpoint de health")
        self.assertEqual(model, Project.Model.SONNET)

    def test_verify_stays_cheap_regardless_of_complexity(self):
        model = choose_model(self.project, Phase.VERIFY, 0, instruction="Refatorar a arquitetura inteira")
        self.assertEqual(model, Project.Model.HAIKU)

    def test_repeated_failures_beat_a_simple_looking_instruction(self):
        """A instrução parecia trivial, mas o trabalho se mostrou difícil."""
        model = choose_model(self.project, Phase.EXECUTE, 2, instruction="Corrigir um typo")
        self.assertEqual(model, Project.Model.OPUS)


class FilePathDetectionTests(SimpleTestCase):
    """A primeira versão da regex era gulosa e nunca casava um caminho:
    `[\\w.-]+` engolia a extensão antes do `\\.` obrigatório."""

    def _files(self, text):
        from apps.agents.model_routing import _FILE_PATH_RE

        return sorted(set(_FILE_PATH_RE.findall(text)))

    def test_paths_with_directories(self):
        self.assertEqual(
            self._files("mexer em src/billing/charge.py e frontend/src/lib/api.ts"),
            ["frontend/src/lib/api.ts", "src/billing/charge.py"],
        )

    def test_bare_filenames_with_code_extensions(self):
        self.assertEqual(self._files("atualizar app.py e models.py"), ["app.py", "models.py"])

    def test_version_numbers_are_not_files(self):
        self.assertEqual(self._files("subir a versão 1.2 para 1.3"), [])


class ComplexityBalanceTests(SimpleTestCase):
    """Os dois casos que a heurística precisa distinguir para não gastar
    Opus à toa: muitos arquivos num pedido mecânico e curto continua médio;
    muitos arquivos com restrições descritas em detalhe sobe."""

    def test_many_files_but_short_and_mechanical_stays_medium(self):
        self.assertEqual(
            instruction_complexity("Atualizar o cabeçalho em app.py, models.py e views.py"),
            MEDIUM,
        )

    def test_many_files_with_detailed_constraints_is_complex(self):
        instrucao = (
            "Atualizar o fluxo de cobrança tocando em src/billing/charge.py, "
            "src/billing/invoice.py e src/api/webhooks.py, mantendo compatibilidade "
            "com os contratos existentes e cobrindo com testes cada caminho de erro "
            "que hoje não tem cobertura nenhuma, incluindo os casos de retentativa "
            "e de pagamento parcial que aparecem em produção."
        )
        self.assertGreater(len(instrucao), LONG_INSTRUCTION_CHARS)  # o sinal de tamanho conta aqui
        self.assertEqual(instruction_complexity(instrucao), COMPLEX)
