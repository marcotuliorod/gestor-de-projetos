import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, type DiffFile } from '../lib/api'
import './Diff.css'

export function Diff() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [files, setFiles] = useState<DiffFile[] | null>(null)
  const [openFiles, setOpenFiles] = useState<Record<number, boolean>>({ 0: true })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [adjustOpen, setAdjustOpen] = useState(false)
  const [adjustText, setAdjustText] = useState('')

  useEffect(() => {
    if (!id) return
    api
      .getTaskRunDiff(id)
      .then((r) => setFiles(r.files))
      .catch(() => setError('Não consegui carregar o diff.'))
  }, [id])

  if (!id) return null

  const toggleFile = (i: number) => setOpenFiles((s) => ({ ...s, [i]: !s[i] }))

  const approve = async () => {
    setBusy(true)
    try {
      await api.approveTaskRun(id)
      navigate(`/runs/${id}`)
    } catch {
      setError('Falha ao aprovar e abrir o PR.')
      setBusy(false)
    }
  }

  const discard = async () => {
    setBusy(true)
    try {
      await api.discardTaskRun(id)
      navigate(`/runs/${id}`)
    } catch {
      setError('Falha ao descartar.')
      setBusy(false)
    }
  }

  const sendAdjustment = async () => {
    if (!adjustText.trim()) return
    setBusy(true)
    try {
      await api.requestChanges(id, adjustText.trim())
      navigate(`/runs/${id}`)
    } catch {
      setError('Falha ao enviar o pedido de ajuste.')
      setBusy(false)
    }
  }

  const totalAdded = (files ?? []).reduce((a, f) => a + f.added, 0)
  const totalRemoved = (files ?? []).reduce((a, f) => a + f.removed, 0)

  return (
    <div className="diff">
      <div className="diff-header">
        <Link to={`/runs/${id}`} className="diff-back">
          ←
        </Link>
        <div className="diff-title">Diff da tarefa</div>
        <div />
      </div>

      <div className="diff-stats">
        <span className="diff-added">+{totalAdded}</span>
        <span className="diff-removed">−{totalRemoved}</span>
        <span className="diff-count">{(files ?? []).length} arquivos</span>
      </div>

      {error && <div className="diff-error">{error}</div>}
      {!files && !error && <div className="diff-loading">Carregando diff…</div>}

      <div className="diff-files">
        {files?.map((f, i) => (
          <div key={f.path} className="diff-file">
            <button className="diff-file-header" onClick={() => toggleFile(i)}>
              <span className="diff-caret">{openFiles[i] ? '▾' : '▸'}</span>
              <span className="diff-path">{f.path}</span>
              <span className="diff-plus">+{f.added}</span>
              <span className="diff-minus">−{f.removed}</span>
            </button>
            {openFiles[i] && (
              <div className="diff-lines">
                {f.lines.map((l, j) => (
                  <div key={j} className={`diff-line diff-line-${l.type}`}>
                    <span>{l.text}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {adjustOpen && (
        <div className="diff-adjust">
          <textarea
            rows={2}
            placeholder="O que precisa mudar?"
            value={adjustText}
            onChange={(e) => setAdjustText(e.target.value)}
          />
          <button className="btn-primary" disabled={busy || !adjustText.trim()} onClick={sendAdjustment}>
            Enviar
          </button>
        </div>
      )}

      <div className="diff-actions">
        <button className="diff-discard" disabled={busy} onClick={discard}>
          Descartar
        </button>
        <button className="btn-secondary diff-adjust-btn" disabled={busy} onClick={() => setAdjustOpen((v) => !v)}>
          Pedir ajustes
        </button>
        <button className="btn-primary diff-approve" disabled={busy} onClick={approve}>
          Aprovar e abrir PR
        </button>
      </div>
    </div>
  )
}
