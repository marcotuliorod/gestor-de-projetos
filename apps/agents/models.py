from django.db import models

from apps.projects.models import Project


class TaskRun(models.Model):
    """Esqueleto de uma execução de tarefa por agente (RF-07..10).

    Reserva o formato dos dados; a orquestração real (GSD Core / Agent SDK
    via subprocess, streaming, diff/PR) entra em fases posteriores.
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
    # Modelo efetivamente usado (auditoria de custo, RF-20).
    model_used = models.CharField(max_length=20, blank=True)
    # Resumo de até 2 linhas do que foi feito (RF-06).
    summary = models.CharField(max_length=280, blank=True)
    pr_url = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project.name}: {self.instruction[:40]}"
