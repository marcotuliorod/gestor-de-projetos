import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, type TaskRun } from '../lib/api'
import { Run } from './Run'

vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/api')>()
  return { ...actual, api: { ...actual.api, getTaskRun: vi.fn(), retryTaskRun: vi.fn() } }
})

function taskRun(overrides: Partial<TaskRun> = {}): TaskRun {
  return {
    id: 1,
    project: 1,
    project_name: 'projeto-teste',
    instruction: 'faz algo',
    urgency: 'now',
    state: 'needs_review',
    model_used: 'sonnet',
    model_override: '',
    summary: '',
    pr_url: '',
    branch_name: 'agent/task-1',
    created_at: '2026-01-01T10:00:00Z',
    updated_at: '2026-01-01T10:05:00Z',
    steps: [
      {
        id: 1,
        phase: 'discuss',
        attempt: 1,
        status: 'done',
        model_used: 'haiku',
        cost_usd: 0.01,
        detail: 'Entendi a instrução.',
        started_at: '2026-01-01T10:00:00Z',
        finished_at: '2026-01-01T10:00:10Z',
      },
      {
        id: 2,
        phase: 'plan',
        attempt: 1,
        status: 'done',
        model_used: 'sonnet',
        cost_usd: 0.02,
        detail: 'Plano: um passo de Execute.',
        started_at: '2026-01-01T10:00:10Z',
        finished_at: '2026-01-01T10:00:20Z',
      },
    ],
    ...overrides,
  }
}

function renderRun() {
  return render(
    <MemoryRouter initialEntries={['/runs/1']}>
      <Routes>
        <Route path="/runs/:id" element={<Run />} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Run — lista de passos colapsável (RF-08)', () => {
  it('começa com todos os passos fechados quando nada está rodando', async () => {
    vi.mocked(api.getTaskRun).mockResolvedValue(taskRun())

    renderRun()

    await screen.findByText('Discuss')
    expect(screen.queryByText('Entendi a instrução.')).not.toBeInTheDocument()
    expect(screen.queryByText('Plano: um passo de Execute.')).not.toBeInTheDocument()
  })

  it('clicar num passo abre o detalhe dele', async () => {
    const user = userEvent.setup()
    vi.mocked(api.getTaskRun).mockResolvedValue(taskRun())

    renderRun()
    await screen.findByText('Discuss')

    await user.click(screen.getByRole('button', { name: /Discuss/ }))

    expect(screen.getByText('Entendi a instrução.')).toBeInTheDocument()
  })

  it('abrir um segundo passo fecha o primeiro — só um por vez', async () => {
    const user = userEvent.setup()
    vi.mocked(api.getTaskRun).mockResolvedValue(taskRun())

    renderRun()
    await screen.findByText('Discuss')

    await user.click(screen.getByRole('button', { name: /Discuss/ }))
    expect(screen.getByText('Entendi a instrução.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Plan/ }))

    expect(screen.getByText('Plano: um passo de Execute.')).toBeInTheDocument()
    expect(screen.queryByText('Entendi a instrução.')).not.toBeInTheDocument()
  })

  it('clicar de novo no passo aberto fecha ele', async () => {
    const user = userEvent.setup()
    vi.mocked(api.getTaskRun).mockResolvedValue(taskRun())

    renderRun()
    await screen.findByText('Discuss')
    const botao = screen.getByRole('button', { name: /Discuss/ })

    await user.click(botao)
    expect(screen.getByText('Entendi a instrução.')).toBeInTheDocument()

    await user.click(botao)
    expect(screen.queryByText('Entendi a instrução.')).not.toBeInTheDocument()
  })

  it('o passo em execução abre sozinho', async () => {
    vi.mocked(api.getTaskRun).mockResolvedValue(
      taskRun({
        state: 'running',
        steps: [
          taskRun().steps[0],
          {
            id: 3,
            phase: 'execute',
            attempt: 1,
            status: 'running',
            model_used: 'sonnet',
            cost_usd: null,
            detail: 'Editando arquivos…',
            started_at: '2026-01-01T10:00:20Z',
            finished_at: null,
          },
        ],
      }),
    )

    renderRun()

    await waitFor(() => expect(screen.getByText('Editando arquivos…')).toBeInTheDocument())
  })

  it('passo sem detalhe não vira botão clicável', async () => {
    vi.mocked(api.getTaskRun).mockResolvedValue(taskRun())

    renderRun()
    await screen.findByText('Discuss')

    // "Verify" e "Ship" ainda não têm step nesta tarefa — nada para expandir.
    expect(screen.getByRole('button', { name: /Verify/ })).toBeDisabled()
  })
})
