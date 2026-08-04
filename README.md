# Gestor de Projetos

Painel para gestão de múltiplos projetos de software, leitura de status real
via git/GitHub e orquestração de agentes Claude Code. Ver PRD para o escopo
completo.

**Estado atual:** Fase 0 (infra local) + esqueleto de backend/API da Fase 1.
Sem integração real com GitHub/agentes e sem frontend ainda.

## Stack

Django (ASGI) + Django REST Framework · PostgreSQL · Celery + Redis
(worker/beat) · Flower · tudo via `docker-compose`.

## Como subir (local)

```bash
cp .env.example .env
# edite DJANGO_SECRET_KEY no .env

docker compose up --build            # sobe db, redis, web, worker, beat, flower
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
```

Serviços:

| URL                          | O quê            |
|------------------------------|------------------|
| http://localhost:8000/healthz | Health check     |
| http://localhost:8000/admin/  | Django admin     |
| http://localhost:8000/api/projects/ | CRUD de projetos (DRF) |
| http://localhost:8000/api/board/    | Board read-only        |
| http://localhost:5555/        | Flower (Celery)  |

## Estrutura

```
config/            projeto Django (settings, celery, asgi, urls)
apps/core/         health check
apps/projects/     Project + CRUD (RF-01/02/03)
apps/status/       StatusSnapshot + Board + coletor stub (RF-04/05/06)
apps/agents/       TaskRun (esqueleto, RF-07..10)
apps/budget/       BudgetWindow (esqueleto, RF-11..13)
frontend/          placeholder — aguarda design-briefs
```

## Testar o coletor de status (stub)

```bash
docker compose run --rm web python manage.py shell -c \
  "from apps.status.tasks import collect_status; from apps.projects.models import Project; \
   p=Project.objects.create(name='Teste'); collect_status.delay(p.id)"
```

O snapshot aparece no admin e em `/api/board/`.

## Fora desta fase

Integração GitHub App/webhooks · execução de agentes (GSD Core / Agent SDK) ·
Headroom proxy · Caveman · Token Budget Scheduler funcional · streaming SSE ao
vivo · frontend/PWA · deploy VPS/Tailscale/Caddy.
