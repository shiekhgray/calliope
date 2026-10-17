import axios from 'axios'

const api = axios.create({ baseURL: '/calliope/api' })

// Attach access token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401, try to refresh once, then redirect to login
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        try {
          const { data } = await axios.post('/calliope/api/auth/refresh', { refresh_token: refresh })
          localStorage.setItem('access_token', data.access_token)
          original.headers.Authorization = `Bearer ${data.access_token}`
          return api(original)
        } catch {
          // refresh failed — clear tokens and go to login
        }
      }
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      // Don't bounce if we're already on the login page — a stray background
      // 401 (e.g. an authed query firing while logged out) would otherwise
      // hard-reload the page and wipe whatever the user is typing.
      if (!window.location.pathname.endsWith('/login')) {
        window.location.href = '/calliope/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
