import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, type ModelChoice, type Project } from '../lib/api'
import './NovoProjeto.css'

const MODELS: { value: ModelChoice; label: string }[] = [
  { value: 'auto', label: 'Automático' },
  { value: 'haiku', label: 'Haiku' },
  { value: 'sonnet', label: 'Sonnet' },
  { value: 'opus', label: 'Opus' },
]

const PERMISSIONS: { key: string; label: string; hint: string }[] = [
  { key: 'allow_bash', label: 'Rodar comandos', hint: 'Deixa o agente usar o terminal dentro do worktree.' },
  { key: 'allow_web', label: 'Acessar a web', hint: 'Deixa o agente buscar e ler páginas durante a tarefa.' },
]

export function EditarProjeto() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [stack, setStack] = useState('')
  const [buildCommand, setBuildCommand] = useState('')
  const [testCommand, setTestCommand] = useState('')
  const [lintCommand, setLintCommand] = useState('')
  const [model, setModel] = useState<ModelChoice>('auto')
  const [weight, setWeight] = useState(1)
  const [permissions, setPermissions] = useState<Record<string, boolean>>({})

  useEffect(() => {
    if (!id) return
    api
      .getProject(id)
      .then((p) => {
        setProject(p)
        setStack(p.stack)
        setBuildCommand(p.build_command)
        setTestCommand(p.test_command)
        setLintCommand(p.lint_command)
        setModel(p.default_model)
        setWeight(p.priority_weight)
        setPermissions({
          allow_bash: (p.agent_permissions?.allow_bash as boolean) ?? true,
          allow_web: (p.agent_permissions?.allow_web as boolean) ?? true,
        })
      })
      .catch(() => setError('Não consegui carregar este projeto.'))
      .finally(() => setLoading(false))
  }, [id])

  const save = async () => {
    if (!id) return
    setSaving(true)
    setError(null)
    try {
      await api.updateProject(id, {
        stack: stack.trim(),
        build_command: buildCommand.trim(),
        test_command: testCommand.trim(),
        lint_command: lintCommand.trim(),
        default_model: model,
        priority_weight: weight,
        agent_permissions: permissions,
      })
      navigate(`/projetos/${id}`)
    } catch {
      setError('Não consegui salvar as alterações. Verifique se a API está no ar.')
      setSaving(false)
    }
  }

  if (loading) return <div className="novo">Carregando…</div>
  if (!project) return <div className="novo">{error ?? 'Projeto não encontrado.'}</div>

  return (
    <div className="novo">
      <button type="button" className="novo-back" onClick={() => navigate(`/projetos/${id}`)}>
        ← {project.name}
      </button>
      <h1>Editar projeto</h1>
      <p className="novo-sub">
        Os comandos são o que o agente roda para verificar o próprio trabalho antes de abrir um PR.
      </p>

      <label className="novo-field">
        <span>Stack</span>
        <input value={stack} onChange={(e) => setStack(e.target.value)} placeholder="ex.: Node · Vite" />
      </label>
      <label className="novo-field">
        <span>Build</span>
        <input value={buildCommand} onChange={(e) => setBuildCommand(e.target.value)} placeholder="opcional" />
      </label>
      <label className="novo-field">
        <span>Testes</span>
        <input value={testCommand} onChange={(e) => setTestCommand(e.target.value)} placeholder="opcional" />
      </label>
      <label className="novo-field">
        <span>Lint</span>
        <input value={lintCommand} onChange={(e) => setLintCommand(e.target.value)} placeholder="opcional" />
      </label>

      <div className="novo-label">Modelo padrão</div>
      <div className="novo-chips">
        {MODELS.map((m) => (
          <button
            key={m.value}
            type="button"
            className={`chip${model === m.value ? ' chip-active' : ''}`}
            onClick={() => setModel(m.value)}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="novo-label">Peso de prioridade</div>
      <div className="novo-weight">
        <button type="button" onClick={() => setWeight((w) => Math.max(1, w - 1))} aria-label="Diminuir peso">
          −
        </button>
        <span>{weight}</span>
        <button type="button" onClick={() => setWeight((w) => Math.min(5, w + 1))} aria-label="Aumentar peso">
          +
        </button>
      </div>

      <div className="novo-label">O que o agente pode fazer</div>
      <div className="perm-list">
        {PERMISSIONS.map((perm) => (
          <label key={perm.key} className="perm-row">
            <input
              type="checkbox"
              checked={permissions[perm.key] ?? true}
              onChange={(e) => setPermissions((p) => ({ ...p, [perm.key]: e.target.checked }))}
            />
            <span className="perm-main">
              <span className="perm-label">{perm.label}</span>
              <span className="perm-hint">{perm.hint}</span>
            </span>
          </label>
        ))}
      </div>

      {error && <div className="novo-error">{error}</div>}

      <button type="button" className="btn-primary novo-submit" onClick={save} disabled={saving}>
        {saving ? 'Salvando…' : 'Salvar alterações'}
      </button>
    </div>
  )
}
