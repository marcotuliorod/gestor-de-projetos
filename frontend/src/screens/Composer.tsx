import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, type Project, type TaskRunUrgency } from '../lib/api'
import './Composer.css'

const SHORTCUTS = [
  'Atualizar dependências',
  'Subir cobertura de testes',
  'Revisar acessibilidade',
  'Corrigir avisos de lint',
]

export function Composer() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const preselected = searchParams.get('project')

  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState<number | null>(preselected ? Number(preselected) : null)
  const [instruction, setInstruction] = useState('')
  const [urgency, setUrgency] = useState<TaskRunUrgency>('now')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.listProjects().then((list) => {
      setProjects(list)
      if (!preselected && list.length > 0) setProjectId(list[0].id)
    })
  }, [preselected])

  const submit = async () => {
    if (!projectId || !instruction.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const run = await api.createTaskRun({ project: projectId, instruction: instruction.trim(), urgency })
      navigate(`/runs/${run.id}`)
    } catch {
      setError('Não consegui criar a tarefa. Verifique se a API está no ar.')
      setSubmitting(false)
    }
  }

  return (
    <div className="composer">
      <h1>Nova tarefa</h1>

      <div className="composer-label">Projeto</div>
      <div className="composer-projects">
        {projects.map((p) => (
          <button
            key={p.id}
            className={`chip${projectId === p.id ? ' chip-active' : ''}`}
            onClick={() => setProjectId(p.id)}
          >
            {p.name}
          </button>
        ))}
      </div>

      <textarea
        className="composer-textarea"
        rows={3}
        placeholder="O que o agente deve fazer?"
        value={instruction}
        onChange={(e) => setInstruction(e.target.value)}
      />

      <div className="composer-shortcuts">
        {SHORTCUTS.map((s) => (
          <button key={s} className="shortcut" onClick={() => setInstruction(s)}>
            {s}
          </button>
        ))}
      </div>

      <div className="composer-label">Urgência</div>
      <div className="segmented">
        <button className={urgency === 'now' ? 'segmented-active' : ''} onClick={() => setUrgency('now')}>
          Agora
        </button>
        <button className={urgency === 'nightly' ? 'segmented-active' : ''} onClick={() => setUrgency('nightly')}>
          Fila noturna
        </button>
      </div>

      {error && <div className="composer-error">{error}</div>}

      <button
        className="btn-primary composer-submit"
        disabled={submitting || !projectId || !instruction.trim()}
        onClick={submit}
      >
        {submitting ? 'Enviando…' : urgency === 'now' ? 'Rodar agora' : 'Adicionar à fila noturna'}
      </button>
    </div>
  )
}
