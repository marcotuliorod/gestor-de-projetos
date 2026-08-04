from django.db import models

from apps.projects.models import Project


class ProjectState(models.TextChoices):
    """Os quatro estados do Board (RF-05), ordenados por urgência."""

    PRECISA_DE_VOCE = "precisa_de_voce", "Precisa de você"
    RODANDO = "rodando", "Rodando"
    EM_DIA = "em_dia", "Em dia"
    PARADO = "parado", "Parado"


# Ordem de urgência para ordenação do Board (menor = mais urgente).
STATE_URGENCY = {
    ProjectState.PRECISA_DE_VOCE: 0,
    ProjectState.RODANDO: 1,
    ProjectState.PARADO: 2,
    ProjectState.EM_DIA: 3,
}


class StatusSnapshot(models.Model):
    """Foto do estado real de um projeto num instante (RF-04/05/06).

    Alimentado pelo coletor de status (task Celery). Nesta fase o coletor
    é um stub; a leitura real via GitHub App/webhooks + git fetch entra depois.
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="snapshots"
    )

    branch = models.CharField(max_length=255, blank=True)
    ahead = models.IntegerField(default=0)
    behind = models.IntegerField(default=0)
    open_prs = models.IntegerField(default=0)
    ci_status = models.CharField(max_length=50, blank=True)
    last_commit = models.CharField(max_length=500, blank=True)
    changed_files = models.IntegerField(default=0)

    state = models.CharField(
        max_length=20,
        choices=ProjectState.choices,
        default=ProjectState.PARADO,
    )

    # Resumo em linguagem natural de até 2 linhas (RF-06).
    summary = models.CharField(max_length=280, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["project", "-created_at"])]

    def __str__(self):
        return f"{self.project.name} @ {self.created_at:%Y-%m-%d %H:%M}"
