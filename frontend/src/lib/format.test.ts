import { describe, expect, it } from 'vitest'
import type { CiCheck, TaskRunStep } from './api'
import { checkLabel, checkTone, formatTokens, stepMeta, timeAgo } from './format'

function step(overrides: Partial<TaskRunStep> = {}): TaskRunStep {
  return {
    id: 1,
    phase: 'execute',
    attempt: 1,
    status: 'done',
    model_used: '',
    cost_usd: null,
    detail: '',
    started_at: null,
    finished_at: null,
    ...overrides,
  }
}

describe('stepMeta', () => {
  it('omite o custo quando não foi medido (modo fake)', () => {
    // Mostrar "$0.00" aqui leria como "essa fase não custou nada" em vez de
    // "o custo não foi medido" — a distinção importa para o RF-22.
    const meta = stepMeta(step({ cost_usd: null, model_used: 'sonnet' }))
    expect(meta).not.toContain('$')
    expect(meta).toContain('sonnet')
  })

  it('inclui o custo real quando presente', () => {
    expect(stepMeta(step({ cost_usd: 0.033 }))).toContain('$0.03')
  })

  it('formata duração em segundos abaixo de um minuto', () => {
    const meta = stepMeta(
      step({ started_at: '2026-01-01T10:00:00Z', finished_at: '2026-01-01T10:00:45Z' }),
    )
    expect(meta).toContain('45s')
  })

  it('formata duração em minutos e segundos acima de um minuto', () => {
    const meta = stepMeta(
      step({ started_at: '2026-01-01T10:00:00Z', finished_at: '2026-01-01T10:01:30Z' }),
    )
    expect(meta).toContain('1m 30s')
  })

  it('sem step nenhum, devolve vazio', () => {
    expect(stepMeta(undefined)).toBe('')
  })
})

describe('formatTokens', () => {
  it('mantém números pequenos como estão', () => {
    expect(formatTokens(842)).toBe('842')
  })

  it('vira "k" a partir de mil', () => {
    expect(formatTokens(1_000)).toBe('1k')
    expect(formatTokens(22_810)).toBe('23k')
  })

  it('vira "M" a partir de um milhão', () => {
    expect(formatTokens(2_500_000)).toBe('2.5M')
  })
})

describe('timeAgo', () => {
  it('menos de um minuto vira "agora"', () => {
    expect(timeAgo(new Date().toISOString())).toBe('agora')
  })

  it('minutos', () => {
    expect(timeAgo(new Date(Date.now() - 5 * 60_000).toISOString())).toBe('há 5 min')
  })

  it('vira horas ao passar de 59 minutos', () => {
    // O ponto de virada é onde erro de um costuma se esconder.
    expect(timeAgo(new Date(Date.now() - 60 * 60_000).toISOString())).toBe('há 1h')
  })

  it('vira dias ao passar de 23 horas', () => {
    expect(timeAgo(new Date(Date.now() - 24 * 60 * 60_000).toISOString())).toBe('há 1 dias')
  })
})

function check(overrides: Partial<CiCheck> = {}): CiCheck {
  return { name: 'backend', conclusion: '', status: 'completed', ...overrides }
}

describe('checkTone/checkLabel', () => {
  it('check em andamento é "run", não "fail"', () => {
    const c = check({ status: 'in_progress', conclusion: '' })
    expect(checkTone(c)).toBe('run')
    expect(checkLabel(c)).toBe('rodando')
  })

  it('check concluído com sucesso', () => {
    const c = check({ conclusion: 'success' })
    expect(checkTone(c)).toBe('ok')
    expect(checkLabel(c)).toBe('passou')
  })

  it('check concluído com falha', () => {
    const c = check({ conclusion: 'failure' })
    expect(checkTone(c)).toBe('fail')
    expect(checkLabel(c)).toBe('falhou')
  })

  it('conclusão desconhecida cai no valor bruto', () => {
    expect(checkLabel(check({ conclusion: 'algo_novo' }))).toBe('algo_novo')
  })
})
