# Gestor de Projetos

Painel para gestão de múltiplos projetos de software, leitura de status real
via git/GitHub e orquestração de agentes Claude Code. Ver PRD para o escopo
completo.

**Estado atual:** Fase 0 (infra local) + backend/API da Fase 1 + frontend React
inicial (Board, Config, detalhe de Projeto) implementando o design de
referência (`design/Gestor de Projetos.dc.html`). Sem integração real com
GitHub/agentes ainda — ver "Fora desta fase".

## Stack

Django (ASGI) + Django REST Framework · PostgreSQL · Celery + Redis
(worker/beat) · Flower · tudo via `docker-compose`. Frontend: React + Vite +
TypeScript + React Router, consumindo a API Django.

## Como subir (local)

Backend:

```bash
cp .env.example .env
# edite DJANGO_SECRET_KEY no .env

docker compose up --build            # sobe db, redis, web, worker, beat, flower
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
```

Frontend (em outro terminal):

```bash
cd frontend
npm install
npm run dev                          # http://localhost:5173, com proxy /api -> :8000
```

Serviços:

| URL | O quê |
|---|---|
| `localhost:5173/` | Frontend (React + Vite) |
| `localhost:8000/healthz` | Health check |
| `localhost:8000/admin/` | Django admin |
| `localhost:8000/api/projects/` | CRUD de projetos (DRF) |
| `localhost:8000/api/board/` | Board read-only |
| `localhost:8000/api/snapshots/?project=<id>` | Histórico de status de um projeto |
| `localhost:5555/` | Flower (Celery) |

## Estrutura

```text
config/            projeto Django (settings, celery, asgi, urls)
apps/core/         health check
apps/projects/     Project + CRUD (RF-01/02/03) + action collect_status
apps/status/       StatusSnapshot + Board + histórico + coletor stub (RF-04/05/06)
apps/agents/       TaskRun (esqueleto, RF-07..10)
apps/budget/       BudgetWindow (esqueleto, RF-11..13)
design/             .dc.html exportados do Claude Design (fonte de verdade de UI)
frontend/           React + Vite + TS — Board, Config, Projeto reais; Fila/Cota
                     como placeholder honesto (backend de agentes/orçamento
                     ainda não existe)
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
