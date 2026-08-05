import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type Project, type StatusSnapshot } from '../lib/api'
import './Projeto.css'

export function Projeto() {
  const { id } = useParams<{ id: string }>()
  const [project, setProject] = useState<Project | null>(null)
  const [history, setHistory] = useState<StatusSnapshot[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    Promise.all([api.getProject(id), api.getSnapshotHistory(id)])
      .then(([p, h]) => {
        setProject(p)
        setHistory(h)
      })
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="projeto-loading">Carregando…</div>
  if (!project) return <div className="projeto-loading">Projeto não encontrado.</div>

  const latest = history[0]

  return (
    <div className="projeto">
      <Link to="/" className="back-link">
        ← Board
      </Link>
      <div className="projeto-header">
        <div>
          <h1>{project.name}</h1>
          <div className="projeto-meta">
            {project.repo_url || 'sem repositório'} {project.stack && `· ${project.stack}`}
          </div>
        </div>
      </div>

      <div className="metrics-grid">
        <Metric label="Branch" value={latest?.branch || '—'} />
        <Metric label="Ahead / behind" value={latest ? `${latest.ahead} ↑ · ${latest.behind} ↓` : '—'} />
        <Metric label="PRs abertos" value={latest ? String(latest.open_prs) : '—'} />
        <Metric label="Arquivos modificados" value={latest ? String(latest.changed_files) : '—'} />
        <Metric label="CI" value={latest?.ci_status || '—'} />
        <Metric label="Modelo padrão" value={project.default_model} />
      </div>

      <div className="section-title">Histórico de status</div>
      {history.length === 0 && <div className="projeto-empty">Nenhum snapshot coletado ainda.</div>}
      <div className="history-list">
        {history.map((h) => (
          <div key={h.id} className="history-row">
            <span className="history-icon">{h.state === 'precisa_de_voce' ? '!' : h.state === 'rodando' ? '…' : '✓'}</span>
            <div className="history-main">
              <div className="history-summary">{h.summary || 'Sem resumo'}</div>
              <div className="history-meta">{new Date(h.created_at).toLocaleString('pt-BR')}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  )
}
