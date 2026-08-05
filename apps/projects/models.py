from django.db import models

from .github_utils import parse_github_repo_url


class Project(models.Model):
    """Um projeto de software gerenciado (RF-01/02/03).

    A detecção automática de stack e a ligação real com o GitHub App
    entram em fase posterior; aqui os campos apenas guardam o que o
    usuário informa no cadastro.
    """

    class Model(models.TextChoices):
        HAIKU = "haiku", "Haiku"
        SONNET = "sonnet", "Sonnet"
        OPUS = "opus", "Opus"
        AUTO = "auto", "Automático (por complexidade)"

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Origem no GitHub. repo_url pode vir de seleção via App ou URL manual.
    repo_url = models.URLField(blank=True)
    # owner/repo derivados de repo_url em save() — usados pelo coletor de
    # status (GitHub API) para não reparsear a URL a cada chamada.
    repo_owner = models.CharField(max_length=200, blank=True)
    repo_name = models.CharField(max_length=200, blank=True)

    # Stack detectada/declarada e comandos sugeridos.
    stack = models.CharField(max_length=200, blank=True)
    build_command = models.CharField(max_length=500, blank=True)
    test_command = models.CharField(max_length=500, blank=True)
    lint_command = models.CharField(max_length=500, blank=True)

    # Orquestração de modelo (seção 8 do PRD): padrão automático.
    default_model = models.CharField(
        max_length=20, choices=Model.choices, default=Model.AUTO
    )
    # Peso na distribuição da cota de tokens (RF-13).
    priority_weight = models.PositiveSmallIntegerField(default=1)

    # Permissões concedidas ao agente neste projeto (formato livre por ora).
    agent_permissions = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority_weight", "name"]

    def save(self, *args, **kwargs):
        if self.repo_url:
            parsed = parse_github_repo_url(self.repo_url)
            if parsed:
                self.repo_owner, self.repo_name = parsed
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
