<!-- Procedência: este documento é o PRD original, recuperado na íntegra
     do histórico da sessão de desenvolvimento em 2026-08-05. O conteúdo
     abaixo não foi editado — divergências entre o que ele especifica e o
     que está implementado hoje estão registradas no README e no relatório
     de status. -->

# PRD — Gestor de Projetos
### Product Requirements Document · v1.0 · Agosto/2026

**Status:** Rascunho para implementação
**Dono do produto:** uso pessoal (single-tenant)
**Documentos relacionados:**
- Design de referência (**prioridade máxima de UI**): [Claude Design — Gestor de Projetos](https://claude.ai/design/p/1b4beff8-50a8-4cc3-90d0-e508f1133fa6?file=Gestor+de+Projetos.dc.html&via=share)
- `design-brief-gestor-de-projetos.md` (design system e telas — usar como fallback/documentação textual onde o link acima não cobrir um detalhe)
- `adendo-v2-gestor-de-projetos.md` (migração, custos, PWA)

> **Nota sobre o link de design:** o link está atrás de login do Claude.ai e não pôde ser lido automaticamente por esta ferramenta. Ele é tratado aqui como **fonte de verdade prioritária** para toda decisão visual — em qualquer conflito entre este PRD/o design-brief textual e o que estiver no arquivo `.dc.html`, **o arquivo de design vence**. Antes da implementação, abra o link e confirme componentes, cores e layout exportados de lá; o design-brief textual deve ser atualizado para refletir divergências encontradas.

---

## 1. Visão geral

Um painel web (evoluindo para PWA) que centraliza a gestão de múltiplos projetos de software, lê status real direto do git/GitHub, e orquestra instâncias do Claude Code em uma VPS para executar tarefas de desenvolvimento — com uso inteligente e comprovadamente eficiente da cota de tokens da assinatura Claude já paga pelo usuário.

## 2. Problema

Ver detalhamento completo nos documentos relacionados. Resumo:
1. Múltiplos projetos, tecnologias e contextos diferentes, sem visão unificada.
2. Pouco tempo disponível para acompanhar cada projeto de perto.
3. Tokens da assinatura sobrando todo mês por falta de uma forma prática de aproveitá-los.
4. Alto custo de retomada de contexto ao voltar a um projeto após um tempo parado.

## 3. Objetivos do produto

| Objetivo | Métrica de sucesso |
|---|---|
| Visão unificada de status real | Todo projeto cadastrado reflete estado do git/GitHub sem intervenção manual |
| Uso eficiente da cota de tokens já paga | Consumo de automação fica dentro da cota, sem exigir upgrade de plano |
| Redução do custo de retomada de contexto | Resumo de 2 linhas por run é suficiente para entender o que mudou |
| Qualidade e confiabilidade do que o agente produz | Toda mudança de código passa por PR revisável, nunca commit direto |
| Operação simples | Interface segue fielmente o design de referência; disparo de tarefa em até 3 toques |

## 4. Escopo

### 4.1 Dentro do escopo (v1)
- Cadastro de projeto existente (repositório GitHub) e criação de projeto novo do zero (fluxos F e G do design-brief).
- Painel de status somente-leitura via GitHub App + webhooks + clones locais.
- Disparo de tarefas para agentes Claude Code rodando na VPS, com streaming ao vivo.
- Revisão de diff e abertura de PR (nunca push direto em `main`).
- Scheduler de orçamento de tokens com reserva pessoal protegida e fila noturna.
- Integração das três ferramentas open-source indicadas (seção 7).
- Roteamento de modelo por complexidade de tarefa (seção 8).
- Práticas de loop e multiagente do Claude Code aplicadas à orquestração (seção 9).
- Web responsivo mobile-first, com base pronta para PWA (manifest + service worker).
- Light mode, dark mode e "de acordo com o sistema".

### 4.2 Fora do escopo (v1)
- Múltiplos usuários/times, autenticação social, contas de terceiros.
- Web Push nativo (fica para fase posterior; notificação via Telegram no lugar).
- Deploy automatizado de produção dos projetos gerenciados (o sistema orquestra desenvolvimento, não é uma plataforma de deploy).

## 4.3 Stack tecnológico (decisão registrada)

| Camada | Escolha | Por quê / opção gratuita |
|---|---|---|
| Backend/API | **Python + Django** | Mesma linguagem do Claude Agent SDK (disponível em Python), do Headroom (`pip install headroom-ai`) e do restante do ecossistema de dados do projeto — reduz o número de runtimes distintos na VPS a Python + Node (este último só para o GSD Core, ver 7.3). |
| Banco de dados | **PostgreSQL** | Gratuito/open source, já era a recomendação original; Django tem suporte de primeira classe via `psycopg`/ORM nativo. |
| Fila de tarefas / jobs | **Celery + Redis** | Substitui a sugestão anterior de BullMQ (que é Node-only). Celery é gratuito, maduro, integra nativamente com Django (`django-celery-beat` para agendamento do Token Budget Scheduler, `django-celery-results` para persistir resultado de tarefas). |
| Broker / pub-sub | **Redis** | Open source, gratuito para autoalojar; usado tanto como broker do Celery quanto como canal pub/sub para o streaming de eventos do agente. |
| Streaming ao navegador | **Django Channels** (WebSocket) ou `StreamingHttpResponse` (SSE) sobre ASGI | Ambos gratuitos e nativos do ecossistema Django; SSE via `StreamingHttpResponse` é suficiente para o caso de uso (ver seção 3.2 do plano técnico original) e mais simples de operar que Channels — usar Channels só se decidirmos por interrupção bidirecional de tarefa no futuro. |
| Monitoramento de fila | **Flower** | Dashboard gratuito e padrão para Celery — substitui o "Bull Board" mencionado no plano técnico original. |
| Containers/isolamento | **Docker** | Gratuito, já definido no plano técnico original. |
| Reverse proxy / TLS | **Caddy** ou **Nginx + Certbot (Let's Encrypt)** | Ambos gratuitos. |
| VPN de acesso | **Tailscale** | Plano pessoal gratuito já cobre o uso (adendo v2, seção 3.2). |
| Erros/observabilidade (opcional) | **Sentry (tier gratuito)** | Nível gratuito cobre volume de uso pessoal; alternativa 100% gratuita é logging estruturado local + Flower. |
| Integração GitHub | **PyGithub** ou `requests` direto contra a API REST/GraphQL do GitHub | Gratuito; GitHub App em si não tem custo de uso na faixa deste projeto. |
| Orquestração de agente (GSD Core) | **Node.js como runtime auxiliar**, invocado via subprocess a partir do worker Celery | GSD Core é distribuído como pacote npm (`@opengsd/gsd-core`); não há necessidade de reescrevê-lo — o worker Python apenas dispara o comando GSD Core (`subprocess.run(...)`) dentro do worktree/container da tarefa e lê os artefatos (`PLAN.md`, `SUMMARY.md`, corpo do PR) que ele produz em disco. Node.js free/open source, sem custo adicional. |

**Regra geral de seleção de ferramentas:** toda peça nova da stack precisa ter uma opção de uso gratuito viável para operação pessoal em VPS própria (self-hosted ou tier free hospedado) — nenhuma ferramenta paga é assumida como obrigatória neste PRD. Onde uma alternativa paga aparecer em pesquisas futuras (ex.: filas gerenciadas, APM pago), ela deve ser tratada como opcional/upgrade, nunca como requisito de v1.

## 5. Personas e caso de uso

**Persona única:** desenvolvedor/gestor técnico individual, múltiplos projetos paralelos, pouco tempo, quer aproveitar tokens ociosos da própria assinatura Claude, prioriza controle e revisão humana antes de qualquer mudança chegar ao repositório principal.

## 6. Requisitos funcionais

### 6.1 Gestão de projetos
- RF-01: Adicionar projeto existente via seleção de repositório GitHub (App já autorizado) ou URL manual, com detecção automática de stack e sugestão de comandos de build/test/lint.
- RF-02: Criar projeto novo do zero: nome, descrição, stack (ou "deixar o agente sugerir"), destino/visibilidade no GitHub, scaffold inicial gerado por uma primeira tarefa de agente.
- RF-03: Editar configuração de um projeto (comandos, modelo padrão, peso de prioridade, permissões do agente).

### 6.2 Status e monitoramento
- RF-04: Coletar e exibir, por projeto: branch atual, ahead/behind, PRs abertos, status de CI, último commit, arquivos modificados, cobertura/lint quando disponível.
- RF-05: Classificar cada projeto em um dos quatro estados (Precisa de você / Rodando / Em dia / Parado) e ordenar o Board por urgência.
- RF-06: Gerar, ao fim de cada execução, um resumo em linguagem natural de até 2 linhas do que foi feito.

### 6.3 Execução de tarefas
- RF-07: Compor e enviar uma nova instrução para um projeto, com urgência "Agora" ou "Fila noturna".
- RF-08: Acompanhar execução em tempo real via streaming (lista de passos colapsável).
- RF-09: Revisar diff gerado e escolher: Aprovar e abrir PR / Pedir ajustes / Descartar.
- RF-10: Nunca permitir push direto para a branch padrão — toda mudança sai como branch + PR.

### 6.4 Orçamento de tokens
- RF-11: Exibir barra de cota semanal sempre visível, com reserva pessoal protegida e projeção de esgotamento.
- RF-12: Pausar automaticamente a fila de baixa prioridade ao atingir limiar configurável (padrão 85%), com aviso explícito.
- RF-13: Permitir ajuste de peso/prioridade por projeto na distribuição da cota.

### 6.5 Notificação
- RF-14: Notificar via bot do Telegram quando uma tarefa concluir, falhar, ou exigir revisão humana.

## 7. Integração das ferramentas open-source indicadas

O usuário pediu explicitamente a incorporação de três projetos. Cada um resolve uma camada diferente do problema de eficiência de tokens — **não são concorrentes entre si**, mas exigem coordenação para não se sobreporem (ver 7.4).

### 7.1 Headroom (`headroomlabs-ai/headroom`) — compressão de contexto de entrada

**O que é:** camada de compressão de contexto que roda como proxy/biblioteca/servidor MCP local, comprimindo saídas de ferramentas, logs, arquivos e trechos de RAG antes de chegarem ao LLM. Documentado com 60–95% de redução em dados JSON e 15–20% em agentes de código, sem alterar a resposta final.

**Onde entra na arquitetura:** como **proxy obrigatório entre o Worker de Agentes e a API da Anthropic**, na VPS.

```
Claude Agent SDK (por sessão/tarefa)
        │
        ▼
  Headroom proxy (headroom proxy --port 8787)
        │  CacheAligner → ContentRouter → SmartCrusher/CodeCompressor/Kompress-base
        ▼
  Anthropic API
```

**Como usar, concretamente:**
- Subir `headroom proxy --port 8787` como serviço systemd na VPS, um processo compartilhado por todos os agentes (não um por tarefa — a compressão e o cache de conteúdo se beneficiam de estado compartilhado).
- Cada sessão do Agent SDK aponta para o proxy via a variável de ambiente de base URL do Anthropic (equivalente a `wrap`), em vez de ir direto para `api.anthropic.com`.
- Ativar `HEADROOM_OUTPUT_SHAPER=1` para também reduzir tokens de **saída** (verbosity steering + effort routing) — ver seção 7.4 sobre conflito com Caveman.
- Rodar `headroom learn` periodicamente sobre o histórico de sessões para gerar automaticamente correções em `CLAUDE.local.md` por projeto — reduz tokens de entrada em sessões futuras.
- Habilitar `SharedContext`/memória cross-agent do Headroom para que múltiplas instâncias que tocam no mesmo projeto (ex.: uma tarefa de bugfix e outra de refactor no mesmo dia) não re-leiam o mesmo contexto do zero.

**Requisito de arquitetura:** RF-15 — todo tráfego de agente para a Anthropic passa pelo Headroom proxy; nenhuma sessão do Agent SDK deve conectar diretamente à API.

**Ressalva:** Headroom roda localmente e não envia dados para fora da VPS (é um proxy local), o que é compatível com a postura de segurança já definida no plano técnico (egress controlado).

### 7.2 Caveman (`JuliusBrussee/caveman`) — compressão de estilo de saída

**O que é:** skill/plugin para Claude Code (entre outros agentes) que reduz tokens de **saída** fazendo o agente responder em estilo comprimido ("caveman-speak"), preservando código, comandos e erros byte-a-byte. Benchmarks documentados: média de 65% de redução de tokens de saída (faixa 22–87%), com o aviso honesto de que a técnica **não reduz tokens de entrada** e adiciona ~1–1,5k tokens de entrada por turno pela própria skill.

**Onde entra na arquitetura:**
- Aplicado ao **CLAUDE.md por projeto** via `/caveman-compress`, que reescreve arquivos de memória (`CLAUDE.md`, `AGENTS.md`) com ~46% menos tokens, mantendo código/URLs/paths intactos — isso é ganho permanente de tokens de entrada em toda sessão futura, sem o overhead de runtime da skill completa.
- Aplicado seletivamente às tarefas onde a resposta textual do agente é longa mas não é o artefato final (ex.: explicações, resumos de PR, mensagens de commit) — não em toda tarefa.
- `/caveman-commit` para gerar mensagens de commit no padrão Conventional Commits, ≤50 caracteres no assunto.
- `/caveman-review` para comentários de PR em uma linha por apontamento.
- `cavecrew-*` (subagentes investigador/builder/reviewer) como opção de subagentes mais econômicos quando o Token Budget Scheduler (seção 8) precisar economizar agressivamente.

**Requisito de arquitetura:** RF-16 — `caveman-compress` roda uma vez por projeto na etapa de cadastro (Fluxo F/G) e é reexecutado sob demanda quando o `CLAUDE.md` crescer além do limite definido (200 linhas, conforme já recomendado no plano técnico).

### 7.3 GSD Core (`open-gsd/gsd-core`) — framework de loop de desenvolvimento por fases

**O que é:** framework de context-engineering e desenvolvimento orientado a especificação que conduz agentes de código (Claude Code incluso) por um loop disciplinado de cinco passos por marco/fase: **Discuss → Plan → Execute → Verify → Ship**. Roda pesquisa, planejamento e execução em subagentes de contexto limpo, mantendo a sessão principal enxuta — resolvendo diretamente o problema de "context rot" (degradação de qualidade conforme o contexto enche).

**Por que é a peça central da orquestração:** este é exatamente o "loop" e o "multiagente" que o usuário pediu na seção 9 — GSD Core não precisa ser reinventado, deve ser **adotado como o motor de execução de cada tarefa da fila**, em vez de o Worker de Agentes chamar o Agent SDK cruamente.

**Onde entra na arquitetura:**

```
Tarefa entra na fila (Task Composer, RF-07)
        │
        ▼
Worker de Agentes invoca GSD Core no worktree da tarefa
        │
        ├─ /gsd-onboard          (primeira vez em um projeto existente — RF-01)
        ├─ /gsd-new-project      (criação de projeto do zero — RF-02)
        │
        └─ loop por fase, para tarefas de desenvolvimento:
             Discuss  → captura decisão de implementação (pode ser preenchido
                        pela própria instrução do Task Composer)
             Plan     → subagente de contexto limpo pesquisa/decompõe/verifica
                        que o plano cabe em uma janela de 200k tokens
             Execute  → subagentes executores rodam em paralelo (ondas),
                        cada um com contexto limpo de 200k
             Verify   → checks automatizados + evidência legível por humano
                        (mapeia para a tela de Run/Diff, RF-08/RF-09)
             Ship     → GSD Core abre o PR com corpo gerado (Summary ·
                        Changes · Requirements Addressed · Verification ·
                        Key Decisions) — consumido diretamente pela tela
                        de Diff/PR (RF-09/RF-10)
```

**Como usar, concretamente:**
- Instalar GSD Core (`npx @opengsd/gsd-core@latest`) dentro de cada worktree de projeto na VPS, configurado para o runtime Claude Code.
- Ao cadastrar um projeto existente (Fluxo F), rodar `/gsd-onboard` como parte da etapa de detecção de stack — GSD Core já produz uma estrutura de planejamento (`​.planning/`) reaproveitável pelas tarefas seguintes.
- Ao criar um projeto do zero (Fluxo G), `/gsd-new-project` substitui o scaffold "cru" descrito no plano técnico anterior — GSD Core já traz o loop Discuss→Plan→Execute→Verify→Ship para a primeira tarefa também.
- Cada instrução enviada pelo Task Composer (RF-07) vira o "Discuss" de uma fase; o restante do loop roda sem intervenção adicional até a etapa de Verify, onde o resultado aparece na tela de Run.
- Comandos de leitura rápida (`/gsd-progress`, `/gsd-stats`) usam `effort: low` — são a fonte primária dos dados do Board (RF-04/RF-05) e **não devem gastar tokens de modelo caro**; roteie-os para Haiku (seção 8).
- Comandos pesados (`/gsd-plan-phase`, `/gsd-execute-phase`, `/gsd-autonomous`) usam `effort: max` e **precisam rodar no nível top da sessão** para reter a ferramenta de spawn de subagentes — não podem ser delegados a um subagente sem Agent tool.

**Requisito de arquitetura:** RF-17 — todo Run (RF-08) mapeia 1:1 para uma fase GSD Core; a tela de Stream Step List (componente 15.4 do design-brief) exibe as cinco etapas do loop (Discuss/Plan/Execute/Verify/Ship) como os "passos" já especificados, em vez de passos genéricos inventados pelo Worker de Agentes.

### 7.4 Coordenação entre as três ferramentas (evitar sobreposição)

Headroom e Caveman **ambos** têm mecanismo de redução de tokens de saída (`HEADROOM_OUTPUT_SHAPER` vs. skill Caveman completa) — rodar os dois ao mesmo tempo na forma "cheia" é redundante e pode até confundir o agente sobre qual estilo seguir. Divisão de responsabilidade recomendada:

| Camada | Ferramenta | Papel exclusivo |
|---|---|---|
| Tokens de **entrada** (contexto, tool outputs, logs) | **Headroom** (proxy) | Única responsável — sempre ativo |
| Tokens de **entrada recorrente** (memória por projeto) | **Caveman** (`/caveman-compress` apenas) | Roda uma vez por projeto/quando `CLAUDE.md` cresce — não a skill completa em runtime |
| Tokens de **saída** (verbosidade da resposta) | **Headroom** (`HEADROOM_OUTPUT_SHAPER=1`) | Escolhido como responsável único de saída, por já estar na mesma camada de proxy e ter medição própria (`headroom output-savings`) |
| Loop de execução, subagentes, planejamento | **GSD Core** | Estrutura o processo de trabalho — não compete com as duas acima, que operam na camada de transporte/prompt |

**Decisão registrada:** não ativar a skill completa do Caveman (`/caveman [lite\|full\|ultra]`) em runtime para não duplicar o output shaper do Headroom. Usar apenas os utilitários pontuais do Caveman (`compress`, `commit`, `review`, `cavecrew-*` como opção de subagente leve) que não conflitam com o proxy.

## 8. Estratégia de orquestração de modelo (seleção por complexidade)

Modelo de decisão em três camadas, aplicado a cada fase do loop GSD Core (seção 7.3):

| Sinal de complexidade | Modelo | Exemplos de uso |
|---|---|---|
| Leitura rápida, sem raciocínio (`effort: low` do GSD) | **Haiku** | `/gsd-progress`, `/gsd-stats`, resumo de 2 linhas pós-run, classificação/triagem de issues, geração de mensagem de commit |
| Desenvolvimento padrão, uma fase, escopo já decomposto (`effort` médio) | **Sonnet** | Fase `Execute` de tarefas rotineiras: implementar função, corrigir bug já isolado, escrever testes |
| Planejamento multi-arquivo, arquitetura, decisões com trade-off (`effort: max` do GSD) | **Opus** | Fase `Plan` de tarefas complexas, `Discuss` de decisões arquiteturais, `/gsd-autonomous` em escopo amplo |

**Regras de implementação:**
- RF-18: o campo `model` de cada chamada ao Agent SDK é determinado pela combinação (tipo de comando GSD Core → `effort` declarado) e (peso de complexidade estimado da instrução do usuário), nunca fixo por projeto.
- RF-19: o usuário pode forçar um modelo específico no Task Composer como override manual (ex.: "usar Opus mesmo sendo tarefa simples"), mas o padrão é automático.
- RF-20: toda mudança de modelo dentro de uma mesma fase (ex.: Plan em Opus, Execute em Sonnet) é registrada no log da tarefa para auditoria de custo.
- Escalonamento automático: se uma fase em Sonnet falhar a verificação (`Verify`) duas vezes seguidas, o sistema escala automaticamente para Opus na terceira tentativa antes de marcar a tarefa como "Precisa de você".

## 9. Práticas eficientes do Claude Code aplicadas

Consolidado do que já está embutido nas seções 7 e 8, explicitado aqui como requisito de arquitetura:

| Prática | Onde é aplicada | Requisito |
|---|---|---|
| **Loop estruturado** (em vez de uma única chamada monolítica) | GSD Core (Discuss→Plan→Execute→Verify→Ship) por fase de tarefa | RF-17 |
| **Multiagente com contexto limpo** | Subagentes de Plan/Execute do GSD Core, cada um com janela de 200k tokens própria; contexto principal fica enxuto | RF-17 |
| **Execução em paralelo (ondas)** | Fase Execute do GSD Core distribui subtarefas independentes em paralelo, respeitando o limite de concorrência do Token Budget Scheduler (adendo v2, seção 2.3) | RF-21 |
| **Roteamento de modelo por esforço** | Seção 8 — `effort: low/max` do GSD Core mapeado para Haiku/Sonnet/Opus | RF-18 |
| **Compressão de contexto de entrada** | Headroom proxy, sempre ativo | RF-15 |
| **Compressão de memória persistente** | `caveman-compress` sobre `CLAUDE.md`/`AGENTS.md` por projeto | RF-16 |
| **Sessões curtas e discretas** | Cada fase GSD Core = uma sessão do Agent SDK; nunca uma sessão "maratona" viva entre tarefas | Já registrado no adendo v2, seção 2.4 |
| **Cache de prompt** | `CLAUDE.md` enxuto e estável no topo do contexto (não reescrito a cada turno) para maximizar cache-hit | RF-22 |
| **Headless/`-p` mode via Agent SDK** | Todo Worker de Agentes usa `query()` do Agent SDK, nunca a UI interativa do Claude Code | Já definido no plano técnico original |
| **Verify antes de Ship** | GSD Core não abre PR sem passar pela etapa de verificação — elimina a ambiguidade "o código foi escrito" vs. "o código funciona" | RF-17 |

## 10. Arquitetura consolidada (atualização do diagrama original)

```
[Celular/Browser] --Tailscale--> [Caddy/Nginx TLS]
                                       |
                 [Django (ASGI)] --SSE/StreamingHttpResponse--> browser
                       |
        +--------------+--------------+
        |                             |
   [PostgreSQL]                [Redis: broker + pub/sub]
        |                             |
        |                    [Celery worker(s)]  ← Flower para monitorar
        |                             |
        |                    git worktree por tarefa (container Docker)
        |                             |
        |                    ┌────────┴────────┐
        |                    │   GSD Core       │  ← loop Discuss→Plan→
        |                    │ (subprocess Node)│    Execute→Verify→Ship
        |                    └────────┬────────┘
        |                             |
        |                    Claude Agent SDK Python (query())
        |                    modelo roteado (Haiku/Sonnet/Opus, seção 8)
        |                             |
        |                    ┌────────┴────────┐
        |                    │  Headroom proxy  │  ← única camada de
        |                    │  (sempre ativo)  │    compressão in/out
        |                    └────────┬────────┘
        |                             |
        |                      Anthropic API
        |
   [status_snapshots]
        ^
        |
   [Coletor de status] <---- GitHub App + webhooks + git fetch (PyGithub)
```

**Notas de implementação:**
- O Django app expõe as views/API (Django REST Framework opcional, se preferir uma API tipada para o frontend) e serve o streaming via `StreamingHttpResponse` lendo de um canal Redis pub/sub alimentado pelo worker Celery.
- Cada task Celery corresponde a uma fase do loop GSD Core (RF-17); o worker invoca o binário `gsd-core`/`claude` via subprocess dentro do container/worktree da tarefa e persiste os artefatos (`PLAN.md`, `SUMMARY.md`, eventos de stream) no Postgres conforme forem produzidos.
- `django-celery-beat` agenda a checagem periódica de status (coletor) e a liberação de tarefas da fila noturna do Token Budget Scheduler (adendo v2, seção 2.3).

`caveman-compress` roda fora do caminho quente — como job de manutenção do `CLAUDE.md`/`AGENTS.md` por projeto, disparado no cadastro (RF-01/RF-02) e quando o arquivo cresce.

## 11. Requisitos não funcionais

- RNF-01: nenhuma sessão de agente escreve na branch padrão do repositório (RF-10).
- RNF-02: toda comunicação de agente com a Anthropic passa pelo Headroom proxy (RF-15).
- RNF-03: interface segue o design de referência do link Claude Design como prioridade sobre qualquer decisão deste documento ou do design-brief textual.
- RNF-04: consumo semanal de tokens nunca ultrapassa a cota sem pausa automática e aviso explícito (RF-12, já definido no adendo v2).
- RNF-05: custo total de infraestrutura permanece dentro do teto de R$250/mês já definido.
- RNF-06: sistema funciona com layout mobile-first e é PWA-ready desde a primeira fase.

## 12. Fases de entrega (atualização do roteiro)

| Fase | Entregável | Ferramentas envolvidas |
|---|---|---|
| 0 | Infraestrutura base (VPS, Tailscale, Postgres, Redis), módulo `authProvider` | — |
| 1 | Painel read-only, RF-01/02 (cadastro de projeto), design conforme link de referência | GitHub App, GSD Core (`/gsd-onboard`, `/gsd-new-project`) |
| 2 | Token Budget Scheduler, disparo de 1ª tarefa, roteamento de modelo (seção 8) | Headroom proxy ativo desde aqui |
| 3 | Streaming ao vivo mapeado às 5 fases do GSD Core, resumo de 2 linhas | GSD Core loop completo, Haiku para resumo |
| 4 | Paralelismo (ondas de Execute), isolamento por container/worktree | GSD Core execução paralela |
| 5 | Diff/PR review, `caveman-compress` de manutenção, `/caveman-commit`/`/caveman-review` | Caveman (utilitários pontuais) |

## 13. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Sobreposição Headroom/Caveman em tokens de saída | Divisão de responsabilidade explícita (seção 7.4) — Caveman completo desativado em runtime |
| GSD Core exigir Agent tool em subagente sem permissão | Comandos `effort: max` sempre rodam no nível top da sessão, nunca delegados (seção 7.3) |
| Dependência de três projetos de terceiros com ritmo de release próprio | Módulo de integração isolado por ferramenta, versão fixada, testado antes de atualizar |
| Link de design não pôde ser lido automaticamente | Confirmar manualmente o conteúdo do link antes da implementação e atualizar o design-brief textual com qualquer divergência |
| Mudança de billing da Anthropic (Agent SDK sair da assinatura) | Interruptor `authProvider` já previsto no adendo v2 |

## 14. Questões em aberto

- Confirmar, ao abrir o link de design, se há componentes/telas que substituem ou detalham os já especificados no design-brief textual — atualizar este PRD após revisão.
- Definir o limiar exato de "complexidade" que decide entre Sonnet e Opus na fase Plan (heurística inicial: número de arquivos tocados + presença de decisão arquitetural explícita na instrução).
- Validar compatibilidade de versão entre GSD Core e a versão do Claude Code/Agent SDK usada na VPS antes do rollout da Fase 1.

---

*Este PRD consolida e substitui, para fins de arquitetura de orquestração e integrações, as seções equivalentes do plano técnico original e do adendo v2. Design visual permanece regido pelo link do Claude Design (prioridade) e pelo design-brief textual (fallback documentado).*
