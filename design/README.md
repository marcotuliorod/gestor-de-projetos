# Design — Gestor de Projetos

Exportados do Claude Design (o link do PRD estava atrás de login; estes são os
arquivos reais). Tratados como **fonte de verdade de UI**, acima do
`design-brief-gestor-de-projetos.md` textual (que ainda não existe neste repo).

## Arquivos

- **`Gestor de Projetos.dc.html`** — versão atual/candidata a fonte de verdade.
  Paleta neutra (zinc/black) via CSS custom properties, com suporte completo a
  `data-theme="dark|light|system"` — implementa o requisito do PRD (§4.1) de
  light/dark/"de acordo com o sistema". Inclui tab bar mobile com FAB de menu
  (Nova tarefa / Novo projeto).
- **`Gestor de Projetos v1 (indigo).dc.html`** — iteração anterior, paleta indigo
  fixa em hex, **sem** alternância de tema (só escuro). Mantido apenas para
  histórico/comparação — não usar como base de implementação.
- **`support.js`** — runtime interno do Claude Design (dc-runtime) usado só para
  pré-visualizar os `.dc.html` no canvas. **Não faz parte do app** — não portar,
  não referenciar do frontend real. O padrão de binding (`{{ expr }}`, `sc-if`,
  `sc-for`, `onClick={{ fn }}`) é sintaxe proprietária do Claude Design, não
  JSX/React puro.

## Como usar isto para implementar o frontend real

Os `.dc.html` não são código de produção — são um protótipo interativo com
estado fake em memória (a classe `Component extends DCLogic` dentro do
`<script data-dc-script>`). O valor está em três camadas, todas para
reimplementar no stack real (React/Vite ou equivalente a decidir):

1. **Design tokens** — bloco `<style>` no `<helmet>`: variáveis CSS
   (`--canvas`, `--surface`, `--text`, `--att`/`--run`/`--ok`/`--info`, etc.),
   tipografia (Inter + JetBrains Mono), raios, animações (`gp-fade`,
   `gp-sheet`, `gp-rise`, `gp-pulse`).
2. **Estrutura de telas e componentes** — o corpo dentro de `<x-dc>`: Board
   (variantes Grupos/Fluxo), Projeto, Run (stream de passos), Diff (review de
   PR), Fila, Cota, Config, Composer (sheet de nova tarefa), Wizard de novo
   projeto (existente vs. do zero), sidebar desktop / tab bar mobile.
3. **Lógica de interação** — o `Component` no script: nomes de estado, transições
   entre telas (`go(screen, extra)`), dados mockados de projetos/runs/fila, e as
   funções que mapeiam 1:1 para os fluxos do PRD (RF-07 a RF-10, RF-14 wizard
   RF-01/02).

Ao implementar: os dados mockados (`RUNS`, `GH_REPOS`, `projects`, `queue`)
saem; os nomes de campo (`status`, `summary`, `when`, `action`, `branch`,
`step/steps`) e os quatro estados do Board (`attention`/`running`/`healthy`/
`idle`) devem bater com os já modelados em `apps/status/models.py`
(`ProjectState`: `precisa_de_voce`/`rodando`/`em_dia`/`parado`) — ajustar nomes
de um lado ou do outro para ficarem consistentes.

## Divergência a resolver

O PRD (RNF-03) diz que o link de design "vence" qualquer conflito. Como havia
duas versões exportadas, tratamos a neutra (`Gestor de Projetos.dc.html`) como
atual por ser a única que implementa o requisito de tema — **mas isso não foi
confirmado com o usuário**. Se a v1 indigo for na verdade a mais recente,
inverta esta prioridade.
