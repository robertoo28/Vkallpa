import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { confirmPasswordReset, requestPasswordReset } from '../api/client.js'
import { useAuth } from '../auth/useAuth.js'
import logo from '../assets/V-Kallpa.png'
import { getDefaultPath } from '../navigation.js'

const Login = () => {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { login, user } = useAuth()
  const initialResetToken = searchParams.get('reset_token') || ''
  const [mode, setMode] = useState(initialResetToken ? 'reset' : 'login')
  const [email, setEmail] = useState('admin')
  const [password, setPassword] = useState('admin')
  const [resetToken, setResetToken] = useState(initialResetToken)
  const [resetPassword, setResetPassword] = useState('')
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (user) {
      navigate(getDefaultPath(user), { replace: true })
    }
  }, [navigate, user])

  const resetFeedback = () => {
    setError(null)
    setNotice(null)
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setLoading(true)
    resetFeedback()

    try {
      const profile = await login(email, password)
      navigate(getDefaultPath(profile), { replace: true })
    } catch {
      setError('Credenciales invalidas o servidor no disponible.')
    } finally {
      setLoading(false)
    }
  }

  const handleRequestReset = async (event) => {
    event.preventDefault()
    setLoading(true)
    resetFeedback()

    try {
      await requestPasswordReset(email)
      setNotice('Si la cuenta existe, enviaremos instrucciones de recuperacion.')
    } catch {
      setError('No se pudo solicitar la recuperacion.')
    } finally {
      setLoading(false)
    }
  }

  const handleConfirmReset = async (event) => {
    event.preventDefault()
    setLoading(true)
    resetFeedback()

    try {
      await confirmPasswordReset(resetToken, resetPassword)
      setMode('login')
      setPassword('')
      setResetPassword('')
      setResetToken('')
      setSearchParams({})
      setNotice('Contrasena actualizada correctamente.')
    } catch {
      setError('El token es invalido o expiro.')
    } finally {
      setLoading(false)
    }
  }

  const showLogin = () => {
    setMode('login')
    resetFeedback()
  }

  const showResetRequest = () => {
    setMode('request')
    resetFeedback()
  }

  return (
    <div className="login-page">
      <div className="login-panel">
        <img src={logo} alt="V-Kallpa" className="login-logo" />
        <h1>Bienvenido</h1>
        <p>Accede a la plataforma de analitica energetica.</p>

        {mode === 'login' && (
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
            {notice && <div className="login-notice">{notice}</div>}
            <button type="submit" disabled={loading}>
              {loading ? 'Ingresando...' : 'Iniciar sesion'}
            </button>
            <button className="login-link-button" type="button" onClick={showResetRequest}>
              Olvide mi contrasena
            </button>
          </form>
        )}

        {mode === 'request' && (
          <form onSubmit={handleRequestReset} className="login-form">
            <label>
              Email
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@empresa.com"
                autoComplete="email"
              />
            </label>
            {error && <div className="login-error">{error}</div>}
            {notice && <div className="login-notice">{notice}</div>}
            <button type="submit" disabled={loading}>
              {loading ? 'Enviando...' : 'Enviar enlace'}
            </button>
            <button className="login-link-button" type="button" onClick={showLogin}>
              Volver al login
            </button>
          </form>
        )}

        {mode === 'reset' && (
          <form onSubmit={handleConfirmReset} className="login-form">
            <label>
              Token
              <input
                value={resetToken}
                onChange={(e) => setResetToken(e.target.value)}
                autoComplete="one-time-code"
                required
              />
            </label>
            <label>
              Nueva contrasena
              <input
                type="password"
                value={resetPassword}
                onChange={(e) => setResetPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
            </label>
            {error && <div className="login-error">{error}</div>}
            {notice && <div className="login-notice">{notice}</div>}
            <button type="submit" disabled={loading}>
              {loading ? 'Guardando...' : 'Guardar contrasena'}
            </button>
            <button className="login-link-button" type="button" onClick={showLogin}>
              Volver al login
            </button>
          </form>
        )}
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
