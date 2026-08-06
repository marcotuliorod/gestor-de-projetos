import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, type TaskRun, type TaskRunPhase } from '../lib/api'
import { stateLabel, stepIcon, stepMeta } from '../lib/format'
import './Run.css'

const PHASE_ORDER: TaskRunPhase[] = ['discuss', 'plan', 'execute', 'verify', 'ship']
const PHASE_LABEL: Record<TaskRunPhase, string> = {
  discuss: 'Discuss',
  plan: 'Plan',
  execute: 'Execute',
  verify: 'Verify',
  ship: 'Ship',
}

export function Run() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [run, setRun] = useState<TaskRun | null>(null)
  const [loading, setLoading] = useState(true)
  // Um passo aberto por vez; null = todos fechados. O passo em execução abre
  // sozinho (ver efeito abaixo) porque é o que a pessoa veio acompanhar.
  const [openPhase, setOpenPhase] = useState<TaskRunPhase | null>(null)
  const [touchedByUser, setTouchedByUser] = useState(false)
  const esRef = useRef<EventSource | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const stateRef = useRef<TaskRun['state'] | null>(null)

  const load = useCallback(async () => {
    if (!id) return
    try {
      const data = await api.getTaskRun(id)
      setRun(data)
      stateRef.current = data.state
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!id) return

    try {
      const es = new EventSource(`/api/task-runs/${id}/stream/`)
      es.onmessage = () => load()
      es.onerror = () => es.close()
      esRef.current = es
    } catch {
      // EventSource indisponível — segue só com o polling abaixo.
    }

    pollRef.current = setInterval(() => {
      if (stateRef.current === 'running' || stateRef.current === 'queued') load()
    }, 3000)

    return () => {
      esRef.current?.close()
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [id, load])

  // Segue o passo em execução enquanto a pessoa não escolher um manualmente —
  // depois disso, respeita a escolha dela e para de mexer.
  useEffect(() => {
    if (touchedByUser || !run) return
    const running = run.steps.find((s) => s.status === 'running')
    if (running) setOpenPhase(running.phase)
  }, [run, touchedByUser])

  const togglePhase = (phase: TaskRunPhase, expanded: boolean) => {
    setTouchedByUser(true)
    setOpenPhase(expanded ? null : phase)
  }

  const retry = async () => {
    if (!id) return
    await api.retryTaskRun(id)
    load()
  }

  if (loading) return <div className="run-loading">Carregando…</div>
  if (!run) return <div className="run-loading">Tarefa não encontrada.</div>

  const stepsByPhase = new Map(run.steps.map((s) => [s.phase, s]))

  return (
    <div className="run">
      <Link to={`/projetos/${run.project}`} className="back-link">
        ← Voltar
      </Link>

      <div className="run-meta">
        <span className="run-repo">{run.project_name}</span>
        <span className={`run-badge run-badge-${run.state}`}>{stateLabel(run.state)}</span>
      </div>
      <h1 className="run-instruction">{run.instruction}</h1>

      <div className="run-steps">
        {PHASE_ORDER.map((phase) => {
          const step = stepsByPhase.get(phase)
          const shipDone = phase === 'ship' && run.state === 'done'
          const status = step?.status ?? (shipDone ? 'done' : 'pending')
          const expandable = Boolean(step?.detail)
          const expanded = expandable && openPhase === phase
          return (
            <div key={phase} className="run-step">
              <div className="run-step-rail">
                <span className={`run-step-icon run-step-icon-${status}`}>{stepIcon(status)}</span>
                <span className="run-step-line" />
              </div>
              <div className="run-step-body">
                <button
                  type="button"
                  className="run-step-header"
                  disabled={!expandable}
                  aria-expanded={expandable ? expanded : undefined}
                  onClick={() => togglePhase(phase, expanded)}
                >
                  <span className="run-step-label">{PHASE_LABEL[phase]}</span>
                  <span className="run-step-meta">
                    {stepMeta(step)}
                    {expandable && <span className="run-step-caret">{expanded ? '▾' : '▸'}</span>}
                  </span>
                </button>
                {expanded && <div className="run-step-detail">{step?.detail}</div>}
              </div>
            </div>
          )
        })}
      </div>

      {run.state === 'needs_review' && (
        <button className="btn-primary run-diff-btn" onClick={() => navigate(`/runs/${run.id}/diff`)}>
          Ver diff
        </button>
      )}

      {run.state === 'failed' && (
        <div className="run-error-card">
          <div>{run.summary || 'A tarefa falhou.'}</div>
          <div className="run-error-actions">
            <button className="btn-primary" onClick={retry}>
              Tentar de novo
            </button>
            <Link to={`/composer?project=${run.project}`} className="btn-secondary">
              Editar instrução
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}

