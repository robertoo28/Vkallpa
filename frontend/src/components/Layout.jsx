import { Outlet } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext.jsx'
import { getRoleLabel } from '../navigation.js'
import Sidebar from './Sidebar.jsx'

const Layout = () => {
  const { user } = useAuth()

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">
        <div className="app-header">
          <div>
            <p className="app-eyebrow">V-Kallpa APP</p>
            <h1 className="app-title">Energy Monitoring & Analytics</h1>
          </div>
          <div className="app-header-meta">
            <div className="app-chip app-chip-muted">{user?.company?.name || 'Vkallpa Core'}</div>
            <div className="app-user-card">
              <strong>{user?.full_name}</strong>
              <span>{getRoleLabel(user?.role)}</span>
            </div>
          </div>
        </div>
        <div className="app-content">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

export default Layout
