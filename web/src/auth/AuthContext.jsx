import { createContext, useContext, useEffect, useState } from 'react'
import axios from 'axios'
import api from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [loggedIn, setLoggedIn] = useState(
    () => !!localStorage.getItem('access_token')
  )
  const [username, setUsername] = useState(
    () => localStorage.getItem('username') ?? ''
  )
  const [userId, setUserId] = useState(
    () => localStorage.getItem('user_id') ? Number(localStorage.getItem('user_id')) : null
  )

  // Recover username/userId for existing sessions that pre-date this storage
  useEffect(() => {
    if (loggedIn && (!username || !userId)) {
      api.get('/auth/me')
        .then(({ data }) => {
          localStorage.setItem('username', data.username)
          localStorage.setItem('user_id', String(data.id))
          setUsername(data.username)
          setUserId(data.id)
        })
        .catch(() => {})
    }
  }, [])

  async function login(user, password) {
    const params = new URLSearchParams({ username: user, password })
    const { data } = await axios.post('/calliope/api/auth/login', params)
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    localStorage.setItem('username', user)
    setUsername(user)
    setLoggedIn(true)
    // Fetch user id after login
    try {
      const me = await api.get('/auth/me')
      localStorage.setItem('user_id', String(me.data.id))
      setUserId(me.data.id)
    } catch {}
  }

  function logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('username')
    localStorage.removeItem('user_id')
    setUsername('')
    setUserId(null)
    setLoggedIn(false)
  }

  return (
    <AuthContext.Provider value={{ loggedIn, username, userId, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
