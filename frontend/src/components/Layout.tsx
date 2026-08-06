import { NavLink, Outlet } from 'react-router-dom'
import { useRegisterSW } from 'virtual:pwa-register/react'
import { CotaBar } from './CotaBar'
import { BoardIcon, ConfigIcon, CotaIcon, FilaIcon } from './icons'
import './Layout.css'

const NAV_ITEMS = [
  { to: '/', label: 'Board', icon: BoardIcon, end: true },
  { to: '/fila', label: 'Fila', icon: FilaIcon, end: false },
  { to: '/cota', label: 'Cota', icon: CotaIcon, end: false },
  { to: '/config', label: 'Config', icon: ConfigIcon, end: false },
]

export function Layout() {
  const { needRefresh: [needRefresh], updateServiceWorker } = useRegisterSW()

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-logo">G</div>
          <div className="sidebar-title">Gestor</div>
        </div>
        <nav className="sidebar-nav">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
              <Icon />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-actions">
          <NavLink to="/projetos/novo" className="btn-primary">
            + Projeto
          </NavLink>
          <CotaBar />
        </div>
      </aside>

      <main className="main-area">
        <CotaBar className="cotabar-mobile" />
        <div className="main-content">
          <Outlet />
        </div>

        <nav className="tab-bar">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => `tab-item${isActive ? ' active' : ''}`}>
              <Icon />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        {needRefresh && (
          <div className="update-toast">
            <span>Nova versão disponível</span>
            <button type="button" className="btn-primary" onClick={() => updateServiceWorker(true)}>
              Atualizar
            </button>
          </div>
        )}
      </main>
    </div>
  )
}
