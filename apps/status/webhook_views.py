import hashlib
import hmac
import json

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.projects.models import Project

from .tasks import collect_status

RELEVANT_EVENTS = {"push", "pull_request", "check_run", "check_suite", "status"}


def _verify_signature(request) -> bool:
    signature = request.headers.get("X-Hub-Signature-256", "")
    secret = settings.GITHUB_WEBHOOK_SECRET.encode()
    expected = "sha256=" + hmac.new(secret, request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@csrf_exempt
@require_POST
def github_webhook(request):
    """Recebe eventos do GitHub e dispara collect_status para os projetos
    afetados (RF-04, tempo real). GitHub não envia CSRF token — a
    autenticidade vem da assinatura HMAC, não do middleware de CSRF.

    Sempre responde 202/204 com assinatura válida (mesmo sem projeto
    correspondente), para o GitHub não desabilitar o webhook por falhas.
    """
    if not _verify_signature(request):
        return HttpResponseForbidden("invalid signature")

    event = request.headers.get("X-GitHub-Event", "")
    if event not in RELEVANT_EVENTS:
        return HttpResponse(status=204)

    payload = json.loads(request.body)
    full_name = (payload.get("repository") or {}).get("full_name", "")
    owner, _, name = full_name.partition("/")

    for project_id in Project.objects.filter(repo_owner=owner, repo_name=name).values_list("id", flat=True):
        collect_status.delay(project_id)

    return HttpResponse(status=202)
