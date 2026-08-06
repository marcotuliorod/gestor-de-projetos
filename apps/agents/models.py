from django.db import models

from apps.projects.models import Project


class TaskRun(models.Model):
    """Uma execução de tarefa por agente (RF-07..10, RF-17..20).

    O loop real (Discuss→Plan→Execute→Verify→Ship) é orquestrado por
    apps.agents.tasks.run_task_run; cada fase gera um TaskRunStep. "Ship"
    (push + abertura de PR) só roda após aprovação humana via /approve/ —
    nunca automaticamente (RNF-01/RF-10).
    """

    class Urgency(models.TextChoices):
        NOW = "now", "Agora"
        NIGHTLY = "nightly", "Fila noturna"

    class State(models.TextChoices):
        QUEUED = "queued", "Na fila"
        RUNNING = "running", "Rodando"
        NEEDS_REVIEW = "needs_review", "Precisa de revisão"
        DONE = "done", "Concluída"
        FAILED = "failed", "Falhou"
        DISCARDED = "discarded", "Descartada"

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="task_runs"
    )
    instruction = models.TextField()
    urgency = models.CharField(
        max_length=10, choices=Urgency.choices, default=Urgency.NOW
    )
    state = models.CharField(
        max_length=15, choices=State.choices, default=State.QUEUED
    )
    # Modelo efetivamente usado (auditoria de custo, RF-20) — visão geral;
    # o registro por fase fica em TaskRunStep.model_used.
    model_used = models.CharField(max_length=20, blank=True)
    # Override manual escolhido no Composer (RF-19). Vazio = decidir
    # automaticamente. Tem precedência sobre Project.default_model: é uma
    # escolha para *esta* tarefa, mais específica que o padrão do projeto.
    model_override = models.CharField(max_length=20, blank=True)
    # Resumo de até 2 linhas do que foi feito (RF-06).
    summary = models.CharField(max_length=280, blank=True)
    pr_url = models.URLField(blank=True)

    # Branch dedicado do worktree deste run e o branch padrão do repo no
    # momento em que o run começou (para diff/push/PR).
    branch_name = models.CharField(max_length=255, blank=True)
    base_branch = models.CharField(max_length=255, blank=True)
    # Texto acumulado de "Pedir ajustes" — realimenta o loop na próxima
    # tentativa de Execute.
    adjustment_instructions = models.TextField(blank=True)
    # Falhas seguidas de Verify — dispara escalonamento Sonnet→Opus (RF-20).
    consecutive_verify_failures = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project.name}: {self.instruction[:40]}"


class TaskRunStep(models.Model):
    """Uma fase (Discuss/Plan/Execute/Verify/Ship) de um TaskRun (RF-17).

    Fonte de verdade para a lista de passos da tela de Run — um GET a
    qualquer momento reconstrói o histórico completo mesmo que o SSE
    perca eventos.
    """

    class Phase(models.TextChoices):
        DISCUSS = "discuss", "Discuss"
        PLAN = "plan", "Plan"
        EXECUTE = "execute", "Execute"
        VERIFY = "verify", "Verify"
        SHIP = "ship", "Ship"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        RUNNING = "running", "Rodando"
        DONE = "done", "Concluído"
        FAILED = "failed", "Falhou"
        SKIPPED = "skipped", "Pulado"

    task_run = models.ForeignKey(
        TaskRun, on_delete=models.CASCADE, related_name="steps"
    )
    phase = models.CharField(max_length=10, choices=Phase.choices)
    attempt = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    model_used = models.CharField(max_length=20, blank=True)
    # Custo real da chamada (ResultMessage.total_cost_usd) — None em modo
    # fake. Base do Token Budget Scheduler (RF-11..13, apps.budget).
    cost_usd = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    # Tokens de prompt reaproveitados do cache e gravados nele (RF-22). Zero
    # em modo fake e quando o cache não pegou — é o número que prova (ou
    # desmente) que a otimização está valendo.
    cache_read_tokens = models.PositiveIntegerField(default=0)
    cache_write_tokens = models.PositiveIntegerField(default=0)
    # Resumo textual curto do que a fase fez/encontrou — nunca o diff.
    detail = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.task_run_id} {self.phase}#{self.attempt} ({self.status})"
