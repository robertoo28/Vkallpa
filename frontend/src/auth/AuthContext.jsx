import { createContext, useContext, useEffect, useMemo, useState } from 'react'

import {
  AUTH_CHANGED_EVENT,
  clearStoredToken,
  fetchCurrentUser,
  getStoredToken,
  login as loginRequest,
  setStoredToken,
} from '../api/client.js'

const AuthContext = createContext(null)

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => getStoredToken())
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const handleAuthChanged = () => {
      setToken(getStoredToken())
    }

    window.addEventListener(AUTH_CHANGED_EVENT, handleAuthChanged)
    return () => window.removeEventListener(AUTH_CHANGED_EVENT, handleAuthChanged)
  }, [])

  useEffect(() => {
    let active = true

    const loadProfile = async () => {
      if (!token) {
        if (active) {
          setUser(null)
          setLoading(false)
        }
        return
      }

      try {
        const profile = await fetchCurrentUser()
        if (active) {
          setUser(profile)
        }
      } catch {
        if (active) {
          setUser(null)
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    setLoading(true)
    loadProfile()

    return () => {
      active = false
    }
  }, [token])

  const login = async (username, password) => {
    const response = await loginRequest(username, password)
    setStoredToken(response.access_token)
    setUser(response.user)
    return response.user
  }

  const logout = () => {
    clearStoredToken()
    setUser(null)
  }

  const refreshUser = async () => {
    const profile = await fetchCurrentUser()
    setUser(profile)
    return profile
  }

  const value = useMemo(
    () => ({
      token,
      user,
      loading,
      login,
      logout,
      refreshUser,
    }),
    [token, user, loading],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider')
  }
  return context
}
