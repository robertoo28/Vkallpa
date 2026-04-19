const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api/v1'
const TOKEN_KEY = 'vk_token'
export const AUTH_CHANGED_EVENT = 'vk-auth-changed'

const emitAuthChanged = () => {
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT))
}

export const getStoredToken = () => localStorage.getItem(TOKEN_KEY)

export const setStoredToken = (token) => {
  localStorage.setItem(TOKEN_KEY, token)
  emitAuthChanged()
}

export const clearStoredToken = () => {
  localStorage.removeItem(TOKEN_KEY)
  emitAuthChanged()
}

export const apiFetch = async (path, options = {}) => {
  const token = getStoredToken()
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  })

  if (res.status === 401) {
    clearStoredToken()
    throw new Error('Unauthorized')
  }

  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || 'Request failed')
  }

  if (res.status === 204) {
    return null
  }

  return res.json()
}

export const login = async (username, password) =>
  apiFetch('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })

export const fetchCurrentUser = async () => apiFetch('/auth/me')
