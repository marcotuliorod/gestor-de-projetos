import { useEffect, useState } from 'react'
import { api, type BudgetState } from '../lib/api'
import './Cota.css'

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${Math.round(n / 1_000)}k`
  return String(n)
}

export function Cota() {
  const [state, setState] = useState<BudgetState | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({ quota_total_usd: '', personal_reserve_pct: '', pause_threshold_pct: '' })
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    api
      .getBudget()
      .then((s) => {
        setState(s)
        setForm({
          quota_total_usd: String(s.quota_total_usd),
          personal_reserve_pct: String(s.personal_reserve_pct),
          pause_threshold_pct: String(s.pause_threshold_pct),
        })
      })
      .catch(() => setError('Não consegui carregar o orçamento.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const saveSettings = async () => {
    setSaving(true)
    try {
      const updated = await api.updateBudgetSettings({
        quota_total_usd: Number(form.quota_total_usd) || 0,
        personal_reserve_pct: Number(form.personal_reserve_pct) || 0,
        pause_threshold_pct: Number(form.pause_threshold_pct) || 0,
      })
      setState(updated)
    } catch {
      setError('Não consegui salvar as configurações.')
    } finally {
      setSaving(false)
    }
  }

  const adjustWeight = async (projectId: number, delta: number) => {
    if (!state) return
    const entry = state.distribution.find((d) => d.project_id === projectId)
    if (!entry) return
    const next = Math.max(1, Math.min(5, entry.priority_weight + delta))
    await api.updateProject(projectId, { priority_weight: next })
    load()
  }

  if (loading) return <div className="cota-loading">Carregando…</div>
  if (error || !state) return <div className="cota-loading cota-error">{error || 'Sem dados.'}</div>

  const maxWeekUsage = Math.max(1, ...state.weeks.map((w) => w.used_usd))

  return (
    <div className="cota">
      <h1>Cota</h1>
      <div className="cota-subtitle">
        {state.quota_total_usd > 0
          ? `No ritmo atual, ${state.pct.toFixed(0)}% do orçamento semanal usado.`
          : 'Defina um orçamento semanal abaixo para começar a acompanhar.'}
      </div>

      <div className="cota-card">
        <div className="cota-card-top">
          <span className="cota-pct">{state.pct.toFixed(0)}% usado</span>
          <span className="cota-reset">reseta em {new Date(state.reset_at).toLocaleString('pt-BR')}</span>
        </div>
        <div className="cota-bar">
          <div className={`cota-bar-fill cota-bar-${state.color}`} style={{ width: `${Math.min(state.pct, 100)}%` }} />
          <div className="cota-bar-reserve" style={{ width: `${state.personal_reserve_pct}%` }} />
        </div>
        <div className="cota-bar-labels">
          <span>consumido (${state.used_usd.toFixed(2)} de ${state.quota_total_usd.toFixed(2)})</span>
          <span>reserva pessoal {state.personal_reserve_pct}%</span>
        </div>
        {state.warn && (
          <div className={`cota-warn cota-warn-${state.color}`}>
            <span className="dot" />
            {state.warn_text}
          </div>
        )}
      </div>

      <div className="cota-section-title">Configuração</div>
      <div className="cota-settings">
        <label>
          Orçamento semanal (USD)
          <input
            type="number"
            step="0.01"
            value={form.quota_total_usd}
            onChange={(e) => setForm((f) => ({ ...f, quota_total_usd: e.target.value }))}
          />
        </label>
        <label>
          Reserva pessoal (%)
          <input
            type="number"
            value={form.personal_reserve_pct}
            onChange={(e) => setForm((f) => ({ ...f, personal_reserve_pct: e.target.value }))}
          />
        </label>
        <label>
          Limiar de pausa (%)
          <input
            type="number"
            value={form.pause_threshold_pct}
            onChange={(e) => setForm((f) => ({ ...f, pause_threshold_pct: e.target.value }))}
          />
        </label>
        <button className="btn-primary" disabled={saving} onClick={saveSettings}>
          {saving ? 'Salvando…' : 'Salvar'}
        </button>
      </div>

      <div className="cota-section-title">Consumo por projeto</div>
      {state.prioritizing_by_weight && (
        <div className="cota-cut-note">
          Enquanto o orçamento estiver apertado, só projetos de peso {state.high_priority_weight} ou mais
          saem na fila noturna. Os demais esperam a próxima noite ou o reset — nada é descartado.
        </div>
      )}
      {state.distribution.length === 0 && <div className="cota-empty">Nenhum gasto registrado nesta janela.</div>}
      <div className="cota-distribution">
        {state.distribution.map((d) => {
          const heldBack = state.prioritizing_by_weight && d.priority_weight < state.high_priority_weight
          return (
          <div key={d.project_id} className={`cota-dist-row${heldBack ? ' cota-dist-held' : ''}`}>
            <div className="cota-dist-top">
              <span className="cota-dist-name">{d.project_name}</span>
              <span className="cota-dist-value">${d.used_usd.toFixed(2)}</span>
            </div>
            {heldBack && <div className="cota-dist-held-label">fora da fila noturna agora</div>}
            <div className="cota-dist-weight">
              <span>Prioridade</span>
              <div className="cota-dist-weight-controls">
                <button onClick={() => adjustWeight(d.project_id, -1)}>−</button>
                <span>{d.priority_weight}</span>
                <button onClick={() => adjustWeight(d.project_id, 1)}>+</button>
              </div>
            </div>
          </div>
          )
        })}
      </div>

      <div className="cota-section-title">Cache de prompt</div>
      <div className="cota-cache">
        {state.cache_tokens.read > 0 ? (
          <>
            <span className="cota-cache-value">{formatTokens(state.cache_tokens.read)}</span>
            <span className="cota-cache-label">
              tokens reaproveitados do cache nesta janela, em vez de cobrados como entrada nova
            </span>
          </>
        ) : (
          <span className="cota-cache-label">
            Nenhum token veio do cache nesta janela — ou nada rodou ainda, ou o cache não está pegando.
          </span>
        )}
      </div>

      <div className="cota-section-title">Últimas semanas</div>
      <div className="cota-weeks">
        {state.weeks.map((w) => (
          <div key={w.week_start} className="cota-week">
            <div className="cota-week-bar" style={{ height: `${Math.max(4, (w.used_usd / maxWeekUsage) * 100)}%` }} />
            <span className="cota-week-label">${w.used_usd.toFixed(0)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
