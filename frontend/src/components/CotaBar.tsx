import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type BudgetSummary } from '../lib/api'
import './CotaBar.css'

/** Barra de cota semanal presente em todas as telas (RF-11).
 *
 *  Busca o resumo enxuto ao montar e sempre que a aba volta ao foco — que é
 *  quando o número costuma estar velho, ao retomar o app no celular horas
 *  depois. Sem polling: o consumo muda quando um agente roda, não a cada
 *  minuto de tela aberta.
 */
export function CotaBar({ className = '' }: { className?: string }) {
  const [state, setState] = useState<BudgetSummary | null>(null)

  const load = useCallback(() => {
    api
      .getBudgetSummary()
      .then(setState)
      .catch(() => {
        /* barra é informativa: falhar em silêncio é melhor que quebrar a navegação */
      })
  }, [])

  useEffect(() => {
    load()
    const onVisible = () => {
      if (document.visibilityState === 'visible') load()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [load])

  // Sem orçamento configurado não há o que mostrar — a tela de Cota é que
  // ensina a definir um.
  if (!state || state.quota_total_usd <= 0) return null

  return (
    <Link to="/cota" className={`cotabar ${className}`.trim()}>
      <div className="cotabar-top">
        <span className="cotabar-title">Cota semanal · {state.pct.toFixed(0)}% usado</span>
      </div>
      <div className="cotabar-track">
        <div
          className={`cotabar-fill cotabar-fill-${state.color}`}
          style={{ width: `${Math.min(state.pct, 100)}%` }}
        />
        {state.personal_reserve_pct > 0 && (
          <div className="cotabar-reserve" style={{ width: `${state.personal_reserve_pct}%` }} />
        )}
      </div>
      {state.projection && <div className="cotabar-projection">{state.projection}</div>}
      {state.warn && <div className={`cotabar-warn cotabar-warn-${state.color}`}>{state.warn_text}</div>}
    </Link>
  )
}
