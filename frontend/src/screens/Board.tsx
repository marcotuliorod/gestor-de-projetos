import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Project, type ProjectState, type StatusSnapshot } from '../lib/api'
import './Board.css'

const STATE_LABEL: Record<ProjectState, string> = {
  precisa_de_voce: 'Precisa de você',
  rodando: 'Rodando',
  em_dia: 'Em dia',
  parado: 'Parado',
}

const STATE_DOT: Record<ProjectState, string> = {
  precisa_de_voce: 'var(--att)',
  rodando: 'var(--run)',
  em_dia: 'var(--ok)',
  parado: 'var(--text3)',
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return 'agora'
  if (minutes < 60) return `há ${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `há ${hours}h`
  return `há ${Math.floor(hours / 24)} dias`
}

export function Board() {
  const [projects, setProjects] = useState<Project[]>([])
  const [snapshots, setSnapshots] = useState<StatusSnapshot[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [healthyOpen, setHealthyOpen] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [projectList, board] = await Promise.all([api.listProjects(), api.getBoard()])
      setProjects(projectList)
      setSnapshots(board)
    } catch {
      setError('Não consegui carregar o Board. Verifique se a API está no ar.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const snapshotByProject = new Map(snapshots.map((s) => [s.project, s]))
  const withoutSnapshot = projects.filter((p) => !snapshotByProject.has(p.id))

  const byState: Record<ProjectState, StatusSnapshot[]> = {
    precisa_de_voce: [],
    rodando: [],
    em_dia: [],
    parado: [],
  }
  for (const s of snapshots) byState[s.state].push(s)

  const healthy = [...byState.em_dia, ...byState.parado]

  const triggerCollectStatus = async (projectId: number) => {
    await api.collectStatus(projectId)
    setTimeout(load, 1500)
  }

  if (loading) return <div className="board-empty">Carregando…</div>
  if (error) return <div className="board-empty board-error">{error}</div>

  const isEmpty = projects.length === 0

  return (
    <div className="board">
      <div className="board-header">
        <div>
          <h1>Board</h1>
          <div className="board-subtitle">
            {isEmpty
              ? 'Nada por aqui ainda'
              : `${byState.precisa_de_voce.length} precisam de você · ${byState.rodando.length} rodando`}
          </div>
        </div>
      </div>

      {isEmpty && (
        <div className="board-empty-state">
          <div className="empty-square" />
          <div className="empty-title">Nenhum projeto ainda</div>
          <div className="empty-text">
            Conecte um repositório existente ou crie um do zero para o agente começar a acompanhar.
          </div>
          <Link to="/config" className="btn-primary" style={{ marginTop: 16, padding: '0 20px', display: 'inline-flex' }}>
            Cadastrar primeiro projeto
          </Link>
        </div>
      )}

      {withoutSnapshot.length > 0 && (
        <section className="board-section">
          <div className="section-heading">
            <span className="dot" style={{ background: 'var(--text3)' }} />
            <span>Sem status ainda</span>
            <span className="count">{withoutSnapshot.length}</span>
          </div>
          <div className="card-grid">
            {withoutSnapshot.map((p) => (
              <article key={p.id} className="card">
                <div className="card-top">
                  <div>
                    <div className="card-name">{p.name}</div>
                    <div className="card-repo">{p.repo_url || 'sem repositório'}</div>
                  </div>
                </div>
                <p className="card-summary">Ainda não coletei o status deste projeto.</p>
                <div className="card-bottom">
                  <span />
                  <button className="btn-primary" style={{ padding: '0 18px' }} onClick={() => triggerCollectStatus(p.id)}>
                    Coletar status
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {byState.precisa_de_voce.length > 0 && (
        <section className="board-section">
          <div className="section-heading">
            <span className="dot" style={{ background: STATE_DOT.precisa_de_voce }} />
            <span>Precisa de você</span>
            <span className="count">{byState.precisa_de_voce.length}</span>
          </div>
          <div className="card-grid">
            {byState.precisa_de_voce.map((s) => (
              <SnapshotCard key={s.id} snapshot={s} />
            ))}
          </div>
        </section>
      )}

      {byState.rodando.length > 0 && (
        <section className="board-section">
          <div className="section-heading">
            <span className="dot" style={{ background: STATE_DOT.rodando }} />
            <span>Rodando agora</span>
            <span className="count">{byState.rodando.length}</span>
          </div>
          <div className="card-grid">
            {byState.rodando.map((s) => (
              <SnapshotCard key={s.id} snapshot={s} />
            ))}
          </div>
        </section>
      )}

      {healthy.length > 0 && (
        <section className="board-section">
          <button className="section-toggle" onClick={() => setHealthyOpen((v) => !v)}>
            <span className="dot" style={{ background: 'var(--text3)' }} />
            <span>Em dia</span>
            <span className="count">{healthy.length}</span>
            <span className="toggle-label">{healthyOpen ? 'esconder' : 'mostrar'}</span>
          </button>
          {healthyOpen && (
            <div className="compact-grid">
              {healthy.map((s) => (
                <Link key={s.id} to={`/projetos/${s.project}`} className="compact-item">
                  <span className="dot" style={{ background: STATE_DOT[s.state] }} />
                  <span className="compact-name">{s.project_name}</span>
                  <span className="compact-when">{timeAgo(s.created_at)}</span>
                </Link>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  )
}

function SnapshotCard({ snapshot }: { snapshot: StatusSnapshot }) {
  return (
    <article className="card">
      <div className="card-top">
        <div>
          <div className="card-name">{snapshot.project_name}</div>
          <div className="card-repo">{snapshot.branch || 'sem branch'}</div>
        </div>
        <div className="card-status">
          <span className="dot" style={{ background: STATE_DOT[snapshot.state] }} />
          <span>{STATE_LABEL[snapshot.state]}</span>
        </div>
      </div>
      <p className="card-summary">{snapshot.summary || 'Sem resumo disponível.'}</p>
      <div className="card-bottom">
        <span className="card-when">{timeAgo(snapshot.created_at)}</span>
        <Link to={`/projetos/${snapshot.project}`} className="btn-primary" style={{ padding: '0 18px' }}>
          Ver projeto
        </Link>
      </div>
    </article>
  )
}
