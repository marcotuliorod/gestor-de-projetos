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

export type ProjectState = 'precisa_de_voce' | 'rodando' | 'em_dia' | 'parado'

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
  state: ProjectState
  summary: string
  created_at: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    throw new Error(`${init?.method ?? 'GET'} ${path} failed: ${res.status}`)
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

  deleteProject: (id: number) =>
    request<void>(`/api/projects/${id}/`, { method: 'DELETE' }),

  getBoard: () => request<StatusSnapshot[]>('/api/board/'),

  getSnapshotHistory: (projectId: number | string) =>
    request<StatusSnapshot[]>(`/api/snapshots/?project=${projectId}`),

  collectStatus: (projectId: number | string) =>
    request<{ queued: boolean }>(`/api/projects/${projectId}/collect_status/`, {
      method: 'POST',
    }),
}
