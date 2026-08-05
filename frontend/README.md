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
  lib/api.ts        cliente HTTP tipado para a API Django (Project, StatusSnapshot,
                      TaskRun/TaskRunStep, DiffFile)
  lib/theme.ts       hook de tema (dark/light/system), persistido em localStorage
  components/        Layout (sidebar desktop + tab bar mobile), ícones
  screens/
    Board.tsx         RF-04/05: lê /api/board/ e /api/projects/, agrupado por estado
    Projeto.tsx        detalhe de um projeto + histórico de snapshots (/api/snapshots/)
    Config.tsx         tema + CRUD de projetos (cadastro manual por ora)
    Composer.tsx        compõe e dispara um TaskRun (projeto, instrução, urgência)
    Run.tsx             passos Discuss/Plan/Execute/Verify/Ship de um TaskRun,
                        via SSE (/stream/) com fallback de polling
    Diff.tsx            revisão de diff (on-demand do worktree) + Aprovar/
                        Pedir ajustes/Descartar
    Fila.tsx            lista real de TaskRuns (RF-07/14)
    Cota.tsx            placeholder honesto — depende do Token Budget Scheduler
  styles/theme.css    tokens de design (cores, tipografia, animações) extraídos
                       do .dc.html — mantenha em sync se o design mudar
```

## O que ainda não existe

- Wizard de projeto novo/existente com detecção automática de stack via
  GitHub App — cadastro de projeto é manual.
- Barra de cota — depende do Token Budget Scheduler (RF-11 a RF-13).
- A chamada real ao Claude Agent SDK (o backend roda em `AGENTS_FAKE_MODE`
  por padrão — ver README raiz).
