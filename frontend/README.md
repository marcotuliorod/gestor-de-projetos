# Frontend — Gestor de Projetos

React + Vite + TypeScript, implementando o design em
`../design/Gestor de Projetos.dc.html` (fonte de verdade de UI — ver
`../design/README.md`) contra a API Django em `../`.

## Rodando localmente

```bash
npm install
npm run dev
```

Abre em `http://localhost:5173`. O `vite.config.ts` faz proxy de `/api/*`
para `http://localhost:8000` (o backend Django) — suba o backend primeiro
(`docker compose up` na raiz do repo).

## Estrutura

```text
src/
  lib/api.ts        cliente HTTP tipado para a API Django (Project, StatusSnapshot)
  lib/theme.ts       hook de tema (dark/light/system), persistido em localStorage
  components/        Layout (sidebar desktop + tab bar mobile), ícones
  screens/
    Board.tsx         RF-04/05: lê /api/board/ e /api/projects/, agrupado por estado
    Projeto.tsx        detalhe de um projeto + histórico de snapshots (/api/snapshots/)
    Config.tsx         tema + CRUD de projetos (cadastro manual por ora)
    Fila.tsx, Cota.tsx  placeholders honestos — dependem de apps ainda
                        não implementados (agents/budget)
  styles/theme.css    tokens de design (cores, tipografia, animações) extraídos
                       do .dc.html — mantenha em sync se o design mudar
```

## O que ainda não existe

- Composer de nova tarefa, Wizard de projeto novo/existente, tela de Run e Diff
  — dependem da execução de agentes (RF-07 a RF-10), que ainda não tem backend.
- Detecção automática de stack via GitHub App — cadastro de projeto é manual.
- Barra de cota — depende do Token Budget Scheduler (RF-11 a RF-13).
