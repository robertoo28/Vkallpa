import { NavLink } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext.jsx'
import logo from '../assets/V-Kallpa.png'
import { getAccessibleMenu, getRoleLabel } from '../navigation.js'

const Sidebar = () => {
  const { logout, user } = useAuth()
  const menu = getAccessibleMenu(user)

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <img src={logo} alt="V-Kallpa" className="sidebar-logo" />
        <div>
          <p className="sidebar-title">V-Kallpa</p>
          <p className="sidebar-subtitle">Plateforme Energie</p>
        </div>
      </div>

      <div className="sidebar-user">
        <strong>{user?.full_name}</strong>
        <span>{getRoleLabel(user?.role)}</span>
        <span>{user?.company?.name || 'Vkallpa'}</span>
      </div>

      <nav className="sidebar-nav">
        {menu.map((section) => (
          <div key={section.name} className="sidebar-section">
            <div className="sidebar-section-title">
              <span className="sidebar-section-icon">{section.icon}</span>
              {section.name}
            </div>
            <div className="sidebar-links">
              {section.items.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    isActive ? 'sidebar-link active' : 'sidebar-link'
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <button className="sidebar-logout" onClick={logout}>
        Deconnexion
      </button>
    </aside>
  )
}

export default Sidebar
