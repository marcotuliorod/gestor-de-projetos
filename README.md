# Gestor de Projetos

Painel para gestão de múltiplos projetos de software, leitura de status real
via git/GitHub e orquestração de agentes Claude Code. Ver PRD para o escopo
completo.

**Estado atual:** Fase 0 (infra local) + backend/API da Fase 1 + frontend React
inicial (Board, Config, detalhe de Projeto) implementando o design de
referência (`design/Gestor de Projetos.dc.html`) + coletor de status real via
GitHub App (webhook + polling). Sem execução de agentes ainda — ver "Fora
desta fase".

## Stack

Django (ASGI) + Django REST Framework · PostgreSQL · Celery + Redis
(worker/beat) · Flower · tudo via `docker-compose`. Frontend: React + Vite +
TypeScript + React Router, consumindo a API Django.

## Como subir (local)

Backend:

```bash
cp .env.example .env
# edite DJANGO_SECRET_KEY no .env
# para o coletor de status real, preencha também GITHUB_APP_ID,
# GITHUB_APP_PRIVATE_KEY_B64, GITHUB_APP_INSTALLATION_ID e
# GITHUB_WEBHOOK_SECRET (ver comentário no .env.example) — sem isso o
# coletor roda e não quebra, mas cria snapshots degradados com o erro
# de autenticação no summary.

docker compose up --build            # sobe db, redis, web, worker, beat, flower
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
docker compose run --rm web python manage.py bootstrap_beat_schedule  # coleta periódica a cada 20min
```

Para o webhook do GitHub apontar para o backend local, use `smee.io` ou
`ngrok` fazendo forward para `http://localhost:8000/api/webhooks/github/`
(configurado como Webhook URL na página da sua GitHub App).

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
| `localhost:8000/api/webhooks/github/` | Webhook do GitHub (POST, HMAC verificado) |
| `localhost:5555/` | Flower (Celery) |

## Estrutura

```text
config/            projeto Django (settings, celery, asgi, urls)
apps/core/         health check
apps/projects/     Project + CRUD (RF-01/02/03) + action collect_status
apps/status/       StatusSnapshot + Board + histórico + coletor real via
                     GitHub App (webhook + polling, RF-04/05/06)
apps/agents/       TaskRun (esqueleto, RF-07..10)
apps/budget/       BudgetWindow (esqueleto, RF-11..13)
design/             .dc.html exportados do Claude Design (fonte de verdade de UI)
frontend/           React + Vite + TS — Board, Config, Projeto reais; Fila/Cota
                     como placeholder honesto (backend de agentes/orçamento
                     ainda não existe)
```

## Testar o coletor de status

```bash
docker compose run --rm web python manage.py shell -c \
  "from apps.status.tasks import collect_status; from apps.projects.models import Project; \
   p=Project.objects.create(name='Teste', repo_url='https://github.com/<owner>/<repo>'); \
   collect_status.delay(p.id)"
```

O snapshot aparece no admin e em `/api/board/`. Com credenciais do GitHub App
válidas no `.env`, o snapshot reflete branch/PRs/CI reais; sem elas, cria um
snapshot degradado com o erro de autenticação no `summary` (não quebra).

Testar o webhook sem GitHub de verdade (assinatura HMAC calculada com o mesmo
`GITHUB_WEBHOOK_SECRET` do `.env`):

```bash
python3 -c "
import hmac, hashlib, json, urllib.request
secret = 'SEU_GITHUB_WEBHOOK_SECRET'
body = json.dumps({'repository': {'full_name': '<owner>/<repo>'}}).encode()
sig = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
req = urllib.request.Request('http://localhost:8000/api/webhooks/github/', data=body, method='POST',
    headers={'Content-Type':'application/json','X-Hub-Signature-256':sig,'X-GitHub-Event':'push'})
print(urllib.request.urlopen(req).status)
"
```

## Fora desta fase

Execução de agentes (GSD Core / Agent SDK) · Headroom proxy · Caveman ·
Token Budget Scheduler funcional · streaming SSE ao vivo · frontend/PWA ·
deploy VPS/Tailscale/Caddy · clone/worktree local (ahead/behind fora do
contexto de um PR aberto fica 0/0 até essa fase).
