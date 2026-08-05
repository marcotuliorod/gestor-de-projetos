import { NavLink, Outlet } from 'react-router-dom'
import { BoardIcon, ConfigIcon, CotaIcon, FilaIcon } from './icons'
import './Layout.css'

const NAV_ITEMS = [
  { to: '/', label: 'Board', icon: BoardIcon, end: true },
  { to: '/fila', label: 'Fila', icon: FilaIcon, end: false },
  { to: '/cota', label: 'Cota', icon: CotaIcon, end: false },
  { to: '/config', label: 'Config', icon: ConfigIcon, end: false },
]

export function Layout() {
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
          <NavLink to="/config" className="btn-primary">
            + Projeto
          </NavLink>
        </div>
      </aside>

      <main className="main-area">
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
      </main>
    </div>
  )
}
