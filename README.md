# Gestor de Projetos

Painel para gestão de múltiplos projetos de software, leitura de status real
via git/GitHub e orquestração de agentes Claude Code. Ver [docs/PRD.md](docs/PRD.md)
para o escopo completo (22 requisitos funcionais, 6 não-funcionais, 6 fases) —
o que já está implementado e onde a implementação diverge do PRD está resumido
abaixo e detalhado em "Desvios em relação ao PRD".

**Estado atual:** Fase 0 (infra local) + backend/API da Fase 1 + frontend React
(Board, Config, Projeto) implementando o design de referência
(`design/Gestor de Projetos.dc.html`) + coletor de status real via GitHub App
(webhook + polling) + **execução de agentes** (RF-07..10, RF-17..20):
Composer → orquestração Discuss→Plan→Execute→Verify (Celery, isolada por
`git worktree`) → Diff review → Aprovar/Pedir ajustes/Descartar, com chamada
real ao Claude Agent SDK (`apps/agents/agent_client.py`) já testada
end-to-end contra a API de verdade — ver "Execução de agentes" abaixo para
os requisitos de segurança do container (não-root + bubblewrap/socat) —
mais o **Token Budget Scheduler** (RF-11..13): orçamento semanal em USD
(a partir do custo real de cada `TaskRunStep`, via `ResultMessage.total_cost_usd`),
com pausa automática da fila noturna ao estourar o limiar — mais
**notificações via Telegram** (RF-14): avisa quando um `TaskRun` precisa de
revisão, falha, tem PR aberto, ou quando a fila noturna é pausada por
orçamento (`apps/core/notifications.py`, best-effort e no-op se não
configurado — ver `.env.example`) — mais **paralelismo de execução seguro**
(RF-21): múltiplos `TaskRun`s rodam de verdade ao mesmo tempo (Celery
`--concurrency`, configurável via `CELERY_WORKER_CONCURRENCY`), com um lock
por projeto (Redis) protegendo o mirror git compartilhado quando duas
execuções concorrentes são do mesmo projeto (`apps/agents/workspace.py`) e
o Board não perde o estado "rodando" enquanto qualquer execução do projeto
ainda está ativa (`apps/agents/tasks.py::_refresh_board_if_idle`) — mais
**frontend instalável (PWA)**: manifest + service worker (`vite-plugin-pwa`),
ícones gerados a partir de `favicon.svg`, e um toast de atualização em vez
de recarregar sozinho no meio de uma revisão (`frontend/src/components/Layout.tsx`).
Sem cache de API — o Board/Fila/Run mostram dados ao vivo, só o app shell é
cacheado.

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
docker compose run --rm web python manage.py bootstrap_beat_schedule          # coleta periódica a cada 20min
docker compose run --rm web python manage.py bootstrap_agents_beat_schedule   # fila noturna de agentes às 02:00
```

**Orçamento semanal:** configure em `POST /api/budget/` (ou pela tela Cota
no frontend) `quota_total_usd`/`personal_reserve_pct`/`pause_threshold_pct` —
por padrão a cota é `$0` (sem teto, nada pausa). O uso é sempre computado
sob demanda a partir de `TaskRunStep.cost_usd` — não há job de "virar a
semana" nem contador que possa dessincronizar.

**Execução de agentes:** `AGENTS_FAKE_MODE=True` (padrão) faz o agente
escrever uma mudança determinística e trivial no worktree em vez de chamar
uma API real. Para rodar com `AGENTS_FAKE_MODE=False` (integração real, já
implementada e testada em `apps/agents/agent_client.py` via o pacote
`claude-agent-sdk`), preencha `ANTHROPIC_API_KEY` no `.env`. Também exige
credenciais reais de GitHub App para o worktree (ver acima) — sem elas, a
preparação falha de forma controlada (`TaskRun` vai para `failed` com um
erro claro, o Board é atualizado imediatamente).

**Requisitos de segurança do container** (descobertos testando contra a API
real, não teóricos — ver `Dockerfile`): o SDK roda sem prompts de aprovação
(`permission_mode="bypassPermissions"`), o que a própria CLI recusa fazer
como root — por isso a imagem roda como usuário não-root (`appuser`). Além
disso, `sandbox={"enabled": True}` (que isola o que os comandos Bash do
agente conseguem tocar, restringindo-o ao worktree) **requer os pacotes
`bubblewrap` e `socat` instalados na imagem** — sem eles o SDK avisa e roda
sem nenhum isolamento, e um teste real confirmou que o agente consegue ler
qualquer arquivo do container (`.env` incluso) nesse caso. Ambos já estão no
`Dockerfile`; se você alterar a imagem base, mantenha os três (usuário
não-root + bubblewrap + socat) ou a execução de agentes fica insegura.

Para o webhook do GitHub apontar para o backend local, use `smee.io` ou
`ngrok` fazendo forward para `http://localhost:8000/api/webhooks/github/`
(configurado como Webhook URL na página da sua GitHub App).

Frontend (em outro terminal):

```bash
cd frontend
npm install
npm run dev                          # http://localhost:5173, com proxy /api -> :8000
```

**PWA:** o service worker só ativa em build de produção (`devOptions.enabled:
false` em `vite.config.ts`) — para testar instalabilidade, use `npm run
build && npm run preview` e abra a aba Application do DevTools (manifest,
service worker, ícones). Os ícones em `frontend/public/pwa-*.png` /
`maskable-icon-512x512.png` / `apple-touch-icon-180x180.png` / `favicon.ico`
são gerados a partir de `favicon.svg` via `npm run generate-pwa-assets`
(`@vite-pwa/assets-generator`) — rode de novo só se trocar a marca.

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
| `localhost:8000/api/task-runs/` | Execução de agentes: criar/listar tarefas |
| `localhost:8000/api/task-runs/<id>/diff/` | Diff computado on-demand do worktree |
| `localhost:8000/api/task-runs/<id>/approve/` | Único endpoint que faz push + abre PR |
| `localhost:8000/api/task-runs/<id>/{request-changes,discard,retry}/` | Ciclo de vida da revisão |
| `localhost:8000/api/task-runs/<id>/stream/` | SSE (best-effort) dos passos da execução |
| `localhost:8000/api/budget/` | GET: estado do orçamento · POST: atualiza settings |
| `localhost:5555/` | Flower (Celery) |

## Estrutura

```text
config/            projeto Django (settings, celery, asgi, urls)
apps/core/         health check
apps/projects/     Project + CRUD (RF-01/02/03) + action collect_status
apps/status/       StatusSnapshot + Board + histórico + coletor real via
                     GitHub App (webhook + polling, RF-04/05/06)
apps/agents/       TaskRun/TaskRunStep, workspace (worktree git), roteamento
                     de modelo, orquestração Discuss→Plan→Execute→Verify e
                     API de execução de agentes (RF-07..10, RF-17..20)
apps/budget/       BudgetSettings (singleton) + tracking.py (agregação de
                     custo por janela semanal) + API (RF-11..13)
design/             .dc.html exportados do Claude Design (fonte de verdade de UI)
frontend/           React + Vite + TS — Board, Config, Projeto, Composer, Run,
                     Diff, Fila e Cota reais
```

## Testar a integração real do Agent SDK (sem precisar de GitHub App)

Chama `agent_client.run_phase()` direto contra um diretório qualquer (não
precisa ser um worktree de verdade nem de credenciais do GitHub) — útil para
validar a chave `ANTHROPIC_API_KEY` e a configuração de sandbox isoladamente:

```bash
docker compose run --rm web python manage.py shell -c "
import tempfile, pathlib
from django.conf import settings
settings.AGENTS_FAKE_MODE = False
from apps.agents.agent_client import run_phase
from apps.agents.models import TaskRunStep
from apps.projects.models import Project
tmp = pathlib.Path(tempfile.mkdtemp())
r = run_phase(phase=TaskRunStep.Phase.EXECUTE, model='haiku', project=Project(name='t'),
    instruction='Crie hello.txt com o conteudo: oi', worktree_path=str(tmp), context={})
print(r.ok, r.detail)
print((tmp / 'hello.txt').read_text())
"
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

Headroom proxy (RF-15/RNF-02) · Caveman (RF-16) · cache de prompt via
`CLAUDE.md` enxuto (RF-22) · criação de projeto do zero com scaffold
(RF-02) · detecção automática de stack e seleção de repo via App (RF-01 —
hoje só URL manual) · detecção automática de plano/limite via conta
Anthropic (não há API confiável para isso) · isolamento por container
Docker por tarefa (usamos `git worktree` num volume compartilhado) ·
suporte offline de dados no PWA (o app é um painel ao vivo — offline
mostraria estado desatualizado) · deploy VPS/Tailscale/Caddy.

## Criar projeto do zero (RF-02)

Este é o único fluxo que **não** usa a GitHub App: uma App não consegue criar
repositório em conta pessoal — o token de instalação não vale para
`POST /user/repos`, e a permissão `administration` só existe para
organizações. Por isso a criação usa um token pessoal (`GITHUB_PAT` no
`.env`), e só ela; todo o resto continua pela App.

Sem `GITHUB_PAT` preenchido, o sistema inteiro funciona normalmente e apenas
esse fluxo responde com um aviso explicando o que falta.

O repositório nasce com commit inicial (`auto_init`), licença e `.gitignore`
da stack; o agente monta estrutura, README, lint e CI na primeira tarefa. Essa
tarefa segue o caminho normal de revisão — nem um repositório recém-criado
escapa da regra de nunca escrever direto na branch padrão (RNF-01/RF-10).

## Desvios em relação ao PRD

Três pontos onde o implementado diverge do que [docs/PRD.md](docs/PRD.md)
especifica — decisões deliberadas, não dívida acidental:

**1. GSD Core abandonado (RF-17).** O PRD previa disparar o GSD Core
(`@opengsd/gsd-core`) via subprocess com comandos `/gsd-*`. Pesquisa contra a
documentação oficial do Claude Code confirmou que slash commands não
funcionam em modo headless (`-p`) — premissa inválida para um worker Celery
sem humano no teclado. A orquestração aqui autora seus próprios prompts por
fase via Agent SDK em vez de depender do GSD Core para execução headless.

**2. Paralelismo é entre tarefas, não "ondas" dentro do Execute (RF-21).** O
PRD descreve subtarefas independentes rodando em paralelo dentro da fase
Execute. O implementado é concorrência entre `TaskRun`s distintos (pool
Celery + lock por projeto) — mais simples e suficiente para uso pessoal, mas
não é a mesma coisa.

**3. Ship não é uma fase do loop.** O loop automático vai até Verify; o push
e a abertura do PR só acontecem no `/approve/`, após revisão humana. Isso é
mais restritivo que o PRD (que descreve 5 fases contínuas) e existe para
garantir RNF-01/RF-10.

**Consequência a registrar:** as três alavancas de eficiência de token do
PRD (RF-15 Headroom, RF-16 Caveman, RF-22 cache de prompt) estão todas
ausentes. O controle de custo hoje é **reativo** — o Token Budget Scheduler
(RF-11..13) mede o custo real de cada `TaskRunStep` e pausa a fila noturna
no limiar, mas nada reduz o consumo por tarefa.
