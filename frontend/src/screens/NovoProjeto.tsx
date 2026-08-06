import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api, type AvailableRepo, type DetectedStack, type ModelChoice } from '../lib/api'
import './NovoProjeto.css'

const MODELS: { value: ModelChoice; label: string }[] = [
  { value: 'auto', label: 'Automático' },
  { value: 'haiku', label: 'Haiku' },
  { value: 'sonnet', label: 'Sonnet' },
  { value: 'opus', label: 'Opus' },
]

const STACK_CHOICES = ['Node · Fastify', 'React · Vite', 'Python · FastAPI', 'Python · Django', 'Go']

type Step = 'path' | 'select' | 'confirm' | 'define'

export function NovoProjeto() {
  const navigate = useNavigate()
  const [step, setStep] = useState<Step>('path')

  // Caminho "criar do zero"
  const [newName, setNewName] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [newStack, setNewStack] = useState('')
  const [isPrivate, setIsPrivate] = useState(true)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const [repos, setRepos] = useState<AvailableRepo[]>([])
  const [loadingRepos, setLoadingRepos] = useState(true)
  const [reposError, setReposError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [manualUrl, setManualUrl] = useState('')

  const [detecting, setDetecting] = useState(false)
  const [detectError, setDetectError] = useState<string | null>(null)
  const [detected, setDetected] = useState<DetectedStack | null>(null)

  const [name, setName] = useState('')
  const [stack, setStack] = useState('')
  const [buildCommand, setBuildCommand] = useState('')
  const [testCommand, setTestCommand] = useState('')
  const [lintCommand, setLintCommand] = useState('')
  const [model, setModel] = useState<ModelChoice>('auto')
  const [weight, setWeight] = useState(3)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    api
      .availableRepos()
      .then(setRepos)
      .catch(() =>
        setReposError(
          'Não consegui listar seus repositórios do GitHub. Você ainda pode colar a URL manualmente abaixo.',
        ),
      )
      .finally(() => setLoadingRepos(false))
  }, [])

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) return repos
    return repos.filter((r) => r.full_name.toLowerCase().includes(term))
  }, [repos, search])

  const runDetection = async (payload: { owner: string; name: string } | { repo_url: string }) => {
    setDetecting(true)
    setDetectError(null)
    try {
      const result = await api.detectStack(payload)
      setDetected(result)
      setName(result.name)
      setStack(result.stack)
      setBuildCommand(result.build_command)
      setTestCommand(result.test_command)
      setLintCommand(result.lint_command)
      setStep('confirm')
    } catch {
      setDetectError('Não consegui ler esse repositório. Confira se a App do GitHub tem acesso a ele.')
    } finally {
      setDetecting(false)
    }
  }

  const save = async () => {
    if (!detected || !name.trim()) return
    setSaving(true)
    setSaveError(null)
    try {
      const project = await api.createProject({
        name: name.trim(),
        repo_url: detected.repo_url,
        stack: stack.trim(),
        build_command: buildCommand.trim(),
        test_command: testCommand.trim(),
        lint_command: lintCommand.trim(),
        default_model: model,
        priority_weight: weight,
      })
      await api.collectStatus(project.id)
      navigate(`/projetos/${project.id}`)
    } catch {
      setSaveError('Não consegui salvar o projeto. Verifique se a API está no ar.')
      setSaving(false)
    }
  }

  const createFromScratch = async () => {
    if (!newName.trim()) return
    setCreating(true)
    setCreateError(null)
    try {
      const result = await api.createFromScratch({
        name: newName.trim(),
        description: newDescription.trim(),
        stack: newStack,
        private: isPrivate,
      })
      navigate(`/runs/${result.task_run_id}`)
    } catch (err) {
      setCreateError(
        err instanceof ApiError ? err.message : 'Não consegui criar o projeto. Verifique se a API está no ar.',
      )
      setCreating(false)
    }
  }

  if (step === 'path') {
    return (
      <div className="novo">
        <h1>Novo projeto</h1>
        <p className="novo-sub">
          Conecte um repositório que já existe ou crie um do zero — o agente cuida do scaffold inicial.
        </p>

        <div className="novo-paths">
          <button type="button" className="novo-path" onClick={() => setStep('select')}>
            <span className="novo-path-title">Já existe</span>
            <span className="novo-path-hint">
              Conectar um repositório do GitHub. Leio a stack e sugiro os comandos.
            </span>
          </button>
          <button type="button" className="novo-path" onClick={() => setStep('define')}>
            <span className="novo-path-title">Criar do zero</span>
            <span className="novo-path-hint">
              Repositório novo, com estrutura, README e CI básica feitos pelo agente.
            </span>
          </button>
        </div>
      </div>
    )
  }

  if (step === 'define') {
    return (
      <div className="novo">
        <button type="button" className="novo-back" onClick={() => setStep('path')}>
          ← Voltar
        </button>
        <h1>Defina o projeto</h1>
        <p className="novo-sub">Uma descrição curta basta — o agente usa isso no scaffold.</p>

        <label className="novo-field">
          <span>Nome</span>
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="ex.: painel-financeiro"
          />
        </label>
        <label className="novo-field">
          <span>Descrição</span>
          <input
            value={newDescription}
            onChange={(e) => setNewDescription(e.target.value)}
            placeholder="o que este projeto faz"
          />
        </label>

        <div className="novo-label">Stack</div>
        <div className="novo-chips">
          {STACK_CHOICES.map((s) => (
            <button
              key={s}
              type="button"
              className={`chip${newStack === s ? ' chip-active' : ''}`}
              onClick={() => setNewStack(s)}
            >
              {s}
            </button>
          ))}
          <button
            type="button"
            className={`chip${newStack === '' ? ' chip-active' : ''}`}
            onClick={() => setNewStack('')}
          >
            Deixar o agente sugerir
          </button>
        </div>

        <div className="novo-label">Visibilidade</div>
        <div className="novo-chips">
          <button
            type="button"
            className={`chip${isPrivate ? ' chip-active' : ''}`}
            onClick={() => setIsPrivate(true)}
          >
            Privado
          </button>
          <button
            type="button"
            className={`chip${!isPrivate ? ' chip-active' : ''}`}
            onClick={() => setIsPrivate(false)}
          >
            Público
          </button>
        </div>

        <div className="novo-note">
          Vou criar o repositório e rodar a primeira tarefa: estrutura de pastas, README, lint e CI básica.
          Como toda tarefa, o resultado vai para revisão — nada é enviado para a branch principal sem sua
          aprovação.
        </div>

        {createError && <div className="novo-error">{createError}</div>}

        <button
          type="button"
          className="btn-primary novo-submit"
          onClick={createFromScratch}
          disabled={creating || !newName.trim()}
        >
          {creating ? 'Criando repositório…' : 'Criar e montar o scaffold'}
        </button>
      </div>
    )
  }

  if (step === 'confirm' && detected) {
    return (
      <div className="novo">
        <button type="button" className="novo-back" onClick={() => setStep('select')}>
          ← Trocar repositório
        </button>
        <h1>Confirme o que detectei</h1>
        <p className="novo-sub">
          Li o repositório <code>{detected.repo_url.replace('https://github.com/', '')}</code>
          {detected.subdir && (
            <>
              {' '}
              e encontrei o projeto em <code>{detected.subdir}/</code>
            </>
          )}
          . Ajuste o que estiver errado.
        </p>

        {!detected.stack && (
          <div className="novo-note">
            Não reconheci a stack pelos arquivos do repositório — preencha os campos abaixo à mão.
          </div>
        )}

        <label className="novo-field">
          <span>Nome</span>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
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

        <div className="novo-note">
          Cadastrar só liga a leitura de status. Nenhum agente roda até você pedir uma tarefa.
        </div>

        {saveError && <div className="novo-error">{saveError}</div>}

        <button type="button" className="btn-primary novo-submit" onClick={save} disabled={saving || !name.trim()}>
          {saving ? 'Salvando…' : 'Adicionar projeto'}
        </button>
      </div>
    )
  }

  return (
    <div className="novo">
      <button type="button" className="novo-back" onClick={() => setStep('path')}>
        ← Voltar
      </button>
      <h1>Selecione o repositório</h1>
      <p className="novo-sub">
        Repositórios onde a App do GitHub está instalada. Eu leio a stack e sugiro os comandos.
      </p>

      <input
        className="novo-search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Buscar repositório…"
      />

      {loadingRepos && <div className="novo-empty">Carregando repositórios…</div>}
      {reposError && <div className="novo-error">{reposError}</div>}

      <div className="novo-repos">
        {filtered.map((repo) => (
          <button
            key={repo.full_name}
            type="button"
            className="novo-repo"
            disabled={repo.already_added || detecting}
            onClick={() => runDetection({ owner: repo.owner, name: repo.name })}
          >
            <div className="novo-repo-main">
              <div className="novo-repo-name">{repo.full_name}</div>
              <div className="novo-repo-meta">
                {repo.private ? 'Privado' : 'Público'}
                {repo.language && ` · ${repo.language}`}
                {repo.already_added && ' · já cadastrado'}
              </div>
            </div>
          </button>
        ))}
      </div>

      {!loadingRepos && filtered.length === 0 && !reposError && (
        <div className="novo-empty">Nenhum repositório com esse nome. Cole a URL completa para conectar manualmente.</div>
      )}

      <div className="novo-label">Ou cole a URL do repositório</div>
      <div className="novo-manual">
        <input
          value={manualUrl}
          onChange={(e) => setManualUrl(e.target.value)}
          placeholder="https://github.com/owner/repo"
        />
        <button
          type="button"
          className="btn-secondary"
          disabled={!manualUrl.trim() || detecting}
          onClick={() => runDetection({ repo_url: manualUrl.trim() })}
        >
          Conectar
        </button>
      </div>

      {detecting && <div className="novo-empty">Lendo o repositório…</div>}
      {detectError && <div className="novo-error">{detectError}</div>}
    </div>
  )
}
