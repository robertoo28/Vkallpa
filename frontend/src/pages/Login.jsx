import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext.jsx'
import logo from '../assets/V-Kallpa.png'
import { getDefaultPath } from '../navigation.js'

const Login = () => {
  const navigate = useNavigate()
  const { login, user } = useAuth()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('admin')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (user) {
      navigate(getDefaultPath(user), { replace: true })
    }
  }, [navigate, user])

  const handleSubmit = async (event) => {
    event.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const profile = await login(username, password)
      navigate(getDefaultPath(profile), { replace: true })
    } catch {
      setError('Identifiants invalides ou serveur indisponible.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-panel">
        <img src={logo} alt="V-Kallpa" className="login-logo" />
        <h1>Bienvenue</h1>
        <p>Accedez a la plateforme d analyse energetique.</p>
        <form onSubmit={handleSubmit} className="login-form">
          <label>
            Utilisateur
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              autoComplete="username"
            />
          </label>
          <label>
            Mot de passe
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="admin"
              autoComplete="current-password"
            />
          </label>
          {error && <div className="login-error">{error}</div>}
          <button type="submit" disabled={loading}>
            {loading ? 'Connexion...' : 'Se connecter'}
          </button>
        </form>
      </div>
      <div className="login-splash">
        <div className="login-splash-card">
          <h2>Suivi energie & performance</h2>
          <p>
            Visualisez la consommation, identifiez les anomalies et pilotez vos
            batiments en temps reel.
          </p>
          <div className="login-splash-metric">
            <span>12%</span>
            <strong>Optimisation cible</strong>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Login
