import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth.js'
import logo from '../assets/V-Kallpa.png'
import { getDefaultPath } from '../navigation.js'

const Login = () => {
  const navigate = useNavigate()
  const { login, user } = useAuth()
  const [email, setEmail] = useState('admin')
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
      const profile = await login(email, password)
      navigate(getDefaultPath(profile), { replace: true })
    } catch {
      setError('Credenciales invalidas o servidor no disponible.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-panel">
        <img src={logo} alt="V-Kallpa" className="login-logo" />
        <h1>Bienvenido</h1>
        <p>Accede a la plataforma de analitica energetica.</p>
        <form onSubmit={handleSubmit} className="login-form">
          <label>
            Email
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@empresa.com"
              autoComplete="email"
            />
          </label>
          <label>
            Contrasena
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
            {loading ? 'Ingresando...' : 'Iniciar sesion'}
          </button>
        </form>
      </div>
      <div className="login-splash">
        <div className="login-splash-card">
          <h2>Energia y performance</h2>
          <p>
            Visualiza el consumo, identifica anomalias y gestiona tus edificios
            en tiempo real.
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
