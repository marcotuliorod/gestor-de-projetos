/** Utilidades de apresentação sem dono, antes duplicadas/espalhadas entre
 *  telas — reunidas aqui para poderem ser testadas uma vez só. */
import type { CiCheck, TaskRun, TaskRunStep } from './api'

const STATE_LABEL: Record<TaskRun['state'], string> = {
  queued: 'Na fila',
  running: 'Rodando',
  needs_review: 'Precisa de revisão',
  done: 'Concluída',
  failed: 'Falhou',
  discarded: 'Descartada',
}

export function stateLabel(state: TaskRun['state']): string {
  return STATE_LABEL[state]
}

/** Duração, modelo e custo real da fase — em branco no que ainda não rodou. */
export function stepMeta(step: TaskRunStep | undefined): string {
  if (!step) return ''
  const parts: string[] = []

  if (step.started_at && step.finished_at) {
    const seconds = Math.max(
      0,
      Math.round((new Date(step.finished_at).getTime() - new Date(step.started_at).getTime()) / 1000),
    )
    parts.push(seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`)
  }
  if (step.model_used) parts.push(step.model_used)
  // Modo fake não tem custo; mostrar "$0.00" ali seria mentira.
  if (step.cost_usd != null) parts.push(`$${Number(step.cost_usd).toFixed(2)}`)

  return parts.join(' · ')
}

export function stepIcon(status: string): string {
  switch (status) {
    case 'done':
      return '✓'
    case 'failed':
      return '✕'
    case 'running':
      return '…'
    default:
      return '○'
  }
}

/** "há 3 min" / "há 2h" / "há 5 dias" — timestamp relativo do Board. */
export function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return 'agora'
  if (minutes < 60) return `há ${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `há ${hours}h`
  return `há ${Math.floor(hours / 24)} dias`
}

/** 1.234 -> "1k", 2.500.000 -> "2.5M" — contagem de tokens da tela de Cota. */
export function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${Math.round(n / 1_000)}k`
  return String(n)
}

const CONCLUSION_LABEL: Record<string, string> = {
  success: 'passou',
  failure: 'falhou',
  cancelled: 'cancelado',
  skipped: 'pulado',
  timed_out: 'estourou o tempo',
  action_required: 'exige ação',
  neutral: 'neutro',
}

export function checkTone(check: CiCheck): 'ok' | 'fail' | 'run' {
  if (check.status !== 'completed') return 'run'
  return check.conclusion === 'success' ? 'ok' : 'fail'
}

export function checkLabel(check: CiCheck): string {
  if (check.status !== 'completed') return 'rodando'
  return CONCLUSION_LABEL[check.conclusion] ?? check.conclusion
}
