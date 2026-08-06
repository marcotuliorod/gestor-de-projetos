import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../lib/api'
import { CotaBar } from './CotaBar'

vi.mock('../lib/api', () => ({
  api: { getBudgetSummary: vi.fn() },
}))

const BASE_STATE = {
  quota_total_usd: 100,
  used_usd: 45,
  pct: 45,
  color: 'normal' as const,
  warn: false,
  warn_text: '',
  projection: '',
  should_pause_nightly: false,
  prioritizing_by_weight: false,
  high_priority_weight: 4,
  cache_tokens: { read: 0, written: 0 },
  personal_reserve_pct: 15,
  pause_threshold_pct: 85,
  window_start: '2026-01-01T00:00:00Z',
  reset_at: '2026-01-08T00:00:00Z',
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('CotaBar', () => {
  it('não renderiza nada sem cota configurada (RF-11)', async () => {
    // Cota zero é o estado padrão do sistema — mostrar uma barra em 0%
    // pareceria dado real em vez de "nada configurado ainda".
    vi.mocked(api.getBudgetSummary).mockResolvedValue({ ...BASE_STATE, quota_total_usd: 0 })

    const { container } = render(
      <MemoryRouter>
        <CotaBar />
      </MemoryRouter>,
    )

    await waitFor(() => expect(api.getBudgetSummary).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('mostra o percentual e a projeção quando há cota', async () => {
    vi.mocked(api.getBudgetSummary).mockResolvedValue({
      ...BASE_STATE,
      projection: 'No ritmo atual, sobra cota até o reset.',
    })

    render(
      <MemoryRouter>
        <CotaBar />
      </MemoryRouter>,
    )

    expect(await screen.findByText(/45% usado/)).toBeInTheDocument()
    expect(screen.getByText('No ritmo atual, sobra cota até o reset.')).toBeInTheDocument()
  })

  it('mostra o aviso só quando warn é verdadeiro', async () => {
    vi.mocked(api.getBudgetSummary).mockResolvedValue({
      ...BASE_STATE,
      color: 'critico',
      warn: true,
      warn_text: 'Fila noturna pausada automaticamente.',
    })

    render(
      <MemoryRouter>
        <CotaBar />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Fila noturna pausada automaticamente.')).toBeInTheDocument()
  })

  it('falha em silêncio quando a API não responde', async () => {
    // A barra é informativa — quebrar a navegação por causa dela seria pior
    // do que simplesmente não aparecer.
    vi.mocked(api.getBudgetSummary).mockRejectedValue(new Error('offline'))

    const { container } = render(
      <MemoryRouter>
        <CotaBar />
      </MemoryRouter>,
    )

    await waitFor(() => expect(api.getBudgetSummary).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })
})
