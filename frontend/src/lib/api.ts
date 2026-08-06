export type ModelChoice = 'haiku' | 'sonnet' | 'opus' | 'auto'

export interface Project {
  id: number
  name: string
  description: string
  repo_url: string
  stack: string
  build_command: string
  test_command: string
  lint_command: string
  default_model: ModelChoice
  priority_weight: number
  agent_permissions: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface AvailableRepo {
  full_name: string
  owner: string
  name: string
  private: boolean
  language: string
  description: string
  updated_at: string
  html_url: string
  already_added: boolean
}

export interface DetectedStack {
  stack: string
  build_command: string
  test_command: string
  lint_command: string
  /** Subpasta onde o manifesto foi encontrado, vazia quando está na raiz. */
  subdir: string
  detected_from: string[]
  owner: string
  name: string
  repo_url: string
}

export type ProjectState = 'precisa_de_voce' | 'rodando' | 'em_dia' | 'parado'

export interface CiCheck {
  name: string
  conclusion: string
  status: string
}

export interface StatusSnapshot {
  id: number
  project: number
  project_name: string
  branch: string
  ahead: number
  behind: number
  open_prs: number
  ci_status: string
  last_commit: string
  changed_files: number
  checks: CiCheck[]
  /** Só vem preenchida quando o CI do projeto publica o número. */
  coverage_pct: number | null
  state: ProjectState
  summary: string
  created_at: string
}

export type TaskRunUrgency = 'now' | 'nightly'
export type TaskRunState = 'queued' | 'running' | 'needs_review' | 'done' | 'failed' | 'discarded'
export type TaskRunPhase = 'discuss' | 'plan' | 'execute' | 'verify' | 'ship'
export type TaskRunStepStatus = 'pending' | 'running' | 'done' | 'failed' | 'skipped'

export interface TaskRunStep {
  id: number
  phase: TaskRunPhase
  attempt: number
  status: TaskRunStepStatus
  model_used: string
  /** Custo real da fase; null em modo fake ou antes de terminar. */
  cost_usd: string | number | null
  detail: string
  started_at: string | null
  finished_at: string | null
}

export interface TaskRun {
  id: number
  project: number
  project_name: string
  instruction: string
  urgency: TaskRunUrgency
  state: TaskRunState
  model_used: string
  /** Modelo forçado no Composer; vazio = decidir automaticamente. */
  model_override: string
  summary: string
  pr_url: string
  branch_name: string
  created_at: string
  updated_at: string
  steps: TaskRunStep[]
}

export interface DiffLine {
  type: 'context' | 'add' | 'del'
  text: string
}

export interface DiffFile {
  path: string
  added: number
  removed: number
  lines: DiffLine[]
}

export type BudgetColor = 'normal' | 'atencao' | 'critico'

export interface BudgetDistributionEntry {
  project_id: number
  project_name: string
  used_usd: number
  priority_weight: number
}

export interface BudgetWeek {
  week_start: string
  used_usd: number
}

export interface BudgetState {
  quota_total_usd: number
  used_usd: number
  pct: number
  color: BudgetColor
  warn: boolean
  warn_text: string
  /** Projeção de esgotamento; vazia quando não há base para projetar. */
  projection: string
  should_pause_nightly: boolean
  /** Faixa em que a fila noturna corta por peso (RF-13). */
  prioritizing_by_weight: boolean
  high_priority_weight: number
  personal_reserve_pct: number
  pause_threshold_pct: number
  window_start: string
  reset_at: string
  distribution: BudgetDistributionEntry[]
  weeks: BudgetWeek[]
}

/** Erro de API que preserva o `detail` explicativo vindo do backend — as
 *  telas mostram esse texto em vez de uma mensagem genérica. */
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = ''
    try {
      const body = (await res.json()) as { detail?: string }
      detail = body?.detail ?? ''
    } catch {
      // resposta sem corpo JSON — segue com a mensagem genérica
    }
    throw new ApiError(res.status, detail || `${init?.method ?? 'GET'} ${path} failed: ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  listProjects: () =>
    request<{ results: Project[] }>('/api/projects/').then((r) => r.results),

  getProject: (id: number | string) => request<Project>(`/api/projects/${id}/`),

  createProject: (data: Partial<Project>) =>
    request<Project>('/api/projects/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateProject: (id: number | string, data: Partial<Project>) =>
    request<Project>(`/api/projects/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),

  deleteProject: (id: number) =>
    request<void>(`/api/projects/${id}/`, { method: 'DELETE' }),

  availableRepos: () => request<AvailableRepo[]>('/api/projects/available-repos/'),

  detectStack: (data: { owner: string; name: string } | { repo_url: string }) =>
    request<DetectedStack>('/api/projects/detect-stack/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  createFromScratch: (data: { name: string; description: string; stack: string; private: boolean }) =>
    request<{ project: Project; task_run_id: number; repo_url: string }>(
      '/api/projects/create-from-scratch/',
      { method: 'POST', body: JSON.stringify(data) },
    ),

  getBoard: () => request<StatusSnapshot[]>('/api/board/'),

  getSnapshotHistory: (projectId: number | string) =>
    request<StatusSnapshot[]>(`/api/snapshots/?project=${projectId}`),

  collectStatus: (projectId: number | string) =>
    request<{ queued: boolean }>(`/api/projects/${projectId}/collect_status/`, {
      method: 'POST',
    }),

  listTaskRuns: () =>
    request<{ results: TaskRun[] }>('/api/task-runs/').then((r) => r.results),

  getTaskRun: (id: number | string) => request<TaskRun>(`/api/task-runs/${id}/`),

  createTaskRun: (data: {
    project: number
    instruction: string
    urgency: TaskRunUrgency
    model_override?: string
  }) => request<TaskRun>('/api/task-runs/', { method: 'POST', body: JSON.stringify(data) }),

  getTaskRunDiff: (id: number | string) =>
    request<{ files: DiffFile[] }>(`/api/task-runs/${id}/diff/`),

  approveTaskRun: (id: number | string) =>
    request<TaskRun>(`/api/task-runs/${id}/approve/`, { method: 'POST' }),

  requestChanges: (id: number | string, instruction: string) =>
    request<TaskRun>(`/api/task-runs/${id}/request-changes/`, {
      method: 'POST',
      body: JSON.stringify({ instruction }),
    }),

  discardTaskRun: (id: number | string) =>
    request<TaskRun>(`/api/task-runs/${id}/discard/`, { method: 'POST' }),

  retryTaskRun: (id: number | string) =>
    request<TaskRun>(`/api/task-runs/${id}/retry/`, { method: 'POST' }),

  getBudget: () => request<BudgetState>('/api/budget/'),

  /** Só o resumo, sem histórico nem distribuição — usado pela barra sempre visível. */
  getBudgetSummary: () => request<BudgetState>('/api/budget/?summary=1'),

  updateBudgetSettings: (data: {
    quota_total_usd?: number
    personal_reserve_pct?: number
    pause_threshold_pct?: number
  }) => request<BudgetState>('/api/budget/', { method: 'POST', body: JSON.stringify(data) }),
}
