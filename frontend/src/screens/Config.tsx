import { useEffect, useState, type FormEvent } from 'react'
import { api, type Project } from '../lib/api'
import { useTheme, type Theme } from '../lib/theme'
import './Config.css'

const THEME_OPTIONS: { value: Theme; label: string }[] = [
  { value: 'light', label: 'Claro' },
  { value: 'dark', label: 'Escuro' },
  { value: 'system', label: 'Sistema' },
]

export function Config() {
  const { theme, setTheme } = useTheme()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [repoUrl, setRepoUrl] = useState('')
  const [stack, setStack] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const load = () => {
    setLoading(true)
    api
      .listProjects()
      .then(setProjects)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setSubmitting(true)
    try {
      const project = await api.createProject({ name: name.trim(), repo_url: repoUrl.trim(), stack: stack.trim() })
      await api.collectStatus(project.id)
      setName('')
      setRepoUrl('')
      setStack('')
      setShowForm(false)
      load()
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (id: number) => {
    await api.deleteProject(id)
    load()
  }

  return (
    <div className="config">
      <h1>Configurações</h1>

      <div className="config-section-title">Tema</div>
      <div className="segmented">
        {THEME_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            className={`segmented-item${theme === opt.value ? ' active' : ''}`}
            onClick={() => setTheme(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div className="config-section-header">
        <div className="config-section-title" style={{ margin: 0 }}>
          Projetos
        </div>
        <button className="btn-secondary" style={{ padding: '0 14px', height: 40 }} onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Cancelar' : '+ Projeto'}
        </button>
      </div>

      {showForm && (
        <form className="project-form" onSubmit={handleCreate}>
          <label>
            Nome
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="ex.: painel-financeiro" required />
          </label>
          <label>
            Repositório (URL, opcional)
            <input value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)} placeholder="https://github.com/..." />
          </label>
          <label>
            Stack (opcional)
            <input value={stack} onChange={(e) => setStack(e.target.value)} placeholder="ex.: Node · Fastify" />
          </label>
          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? 'Criando…' : 'Criar projeto'}
          </button>
        </form>
      )}

      <div className="list-card">
        {loading && <div className="list-empty">Carregando…</div>}
        {!loading && projects.length === 0 && <div className="list-empty">Nenhum projeto cadastrado.</div>}
        {projects.map((p) => (
          <div key={p.id} className="list-row">
            <div className="list-row-main">
              <div className="list-row-name">{p.name}</div>
              <div className="list-row-meta">
                {p.default_model} · peso {p.priority_weight}
                {p.stack ? ` · ${p.stack}` : ''}
              </div>
            </div>
            <button className="list-row-delete" onClick={() => handleDelete(p.id)} aria-label={`Remover ${p.name}`}>
              ✕
            </button>
          </div>
        ))}
      </div>

      <div className="config-section-title">Integrações</div>
      <div className="list-card">
        <div className="list-row">
          <div className="list-row-main">
            <div className="list-row-name">GitHub App</div>
          </div>
          <span className="badge-pending">não configurado</span>
        </div>
        <div className="list-row">
          <div className="list-row-main">
            <div className="list-row-name">Bot do Telegram</div>
          </div>
          <span className="badge-pending">não configurado</span>
        </div>
      </div>
    </div>
  )
}
