import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type TaskRun } from '../lib/api'
import './Fila.css'

const STATE_LABEL: Record<TaskRun['state'], string> = {
  queued: 'Na fila',
  running: 'Rodando',
  needs_review: 'Precisa de revisão',
  done: 'Concluída',
  failed: 'Falhou',
  discarded: 'Descartada',
}

export function Fila() {
  const [runs, setRuns] = useState<TaskRun[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .listTaskRuns()
      .then(setRuns)
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="fila">
      <div className="fila-header">
        <h1>Fila</h1>
        <Link to="/composer" className="btn-primary" style={{ padding: '0 16px', display: 'inline-flex' }}>
          Nova tarefa
        </Link>
      </div>
      <div className="fila-subtitle">
        {runs.length} {runs.length === 1 ? 'tarefa' : 'tarefas'} · a fila noturna roda às 02:00
      </div>

      {loading && <div className="fila-empty">Carregando…</div>}
      {!loading && runs.length === 0 && (
        <div className="fila-empty">
          <div>Nenhuma tarefa ainda.</div>
        </div>
      )}

      <div className="fila-list">
        {runs.map((r) => (
          <Link key={r.id} to={`/runs/${r.id}`} className="fila-row">
            <div className="fila-row-main">
              <div className="fila-row-top">
                <span className="fila-project">{r.project_name}</span>
                <span className="fila-urgency">{r.urgency === 'now' ? 'Agora' : 'Noturna'}</span>
              </div>
              <div className="fila-instruction">{r.instruction}</div>
            </div>
            <span className={`fila-state fila-state-${r.state}`}>{STATE_LABEL[r.state]}</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
