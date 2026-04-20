const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api/v1'
const TOKEN_KEY = 'vk_access_token'
const LEGACY_TOKEN_KEY = 'vk_token'
const REFRESH_TOKEN_KEY = 'vk_refresh_token'
export const AUTH_CHANGED_EVENT = 'vk-auth-changed'

const emitAuthChanged = () => {
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT))
}

export const getStoredToken = () =>
  localStorage.getItem(TOKEN_KEY) || localStorage.getItem(LEGACY_TOKEN_KEY)

export const getStoredRefreshToken = () => localStorage.getItem(REFRESH_TOKEN_KEY)

export const setStoredToken = (token) => {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.removeItem(LEGACY_TOKEN_KEY)
  emitAuthChanged()
}

export const setStoredSession = (accessToken, refreshToken) => {
  localStorage.setItem(TOKEN_KEY, accessToken)
  localStorage.removeItem(LEGACY_TOKEN_KEY)
  if (refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  }
  emitAuthChanged()
}

export const clearStoredSession = () => {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(LEGACY_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  emitAuthChanged()
}

export const clearStoredToken = clearStoredSession

const parseJsonResponse = async (res) => {
  if (res.status === 204) {
    return null
  }
  return res.json()
}

export const refreshSession = async () => {
  const refreshToken = getStoredRefreshToken()
  if (!refreshToken) {
    return null
  }

  try {
    const response = await apiFetch('/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
      skipAuth: true,
      skipRefresh: true,
    })
    setStoredSession(response.access_token, response.refresh_token)
    return response
  } catch {
    clearStoredSession()
    return null
  }
}

export const apiFetch = async (path, options = {}) => {
  const {
    headers: optionHeaders = {},
    skipAuth = false,
    skipRefresh = false,
    ...fetchOptions
  } = options

  const buildHeaders = (token) => {
    const headers = {
      'Content-Type': 'application/json',
      ...optionHeaders,
    }

    if (token) {
      headers.Authorization = `Bearer ${token}`
    }

    return headers
  }

  const send = (token) =>
    fetch(`${API_BASE}${path}`, {
      ...fetchOptions,
      headers: buildHeaders(token),
    })

  let res = await send(skipAuth ? null : getStoredToken())

  if (res.status === 401 && !skipRefresh) {
    const refreshed = await refreshSession()
    if (refreshed) {
      res = await send(refreshed.access_token)
    }
  }

  if (res.status === 401) {
    clearStoredSession()
    throw new Error('Unauthorized')
  }

  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || 'Request failed')
  }

  return parseJsonResponse(res)
}

export const login = async (email, password) =>
  apiFetch('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
    skipAuth: true,
    skipRefresh: true,
  })

export const fetchCurrentUser = async () => apiFetch('/auth/me')
