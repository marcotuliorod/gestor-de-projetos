import './Placeholder.css'

export function Fila() {
  return (
    <div className="placeholder">
      <h1>Fila</h1>
      <div className="placeholder-box">
        <div className="placeholder-box-title">Ainda não há execução de agentes.</div>
        <div className="placeholder-box-hint">
          A fila de tarefas (RF-07/RF-14) depende do worker de agentes, que entra numa fase posterior.
        </div>
      </div>
    </div>
  )
}
