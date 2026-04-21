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

  // Recover username for existing sessions that pre-date username storage
  useEffect(() => {
    if (loggedIn && !username) {
      api.get('/auth/me')
        .then(({ data }) => {
          localStorage.setItem('username', data.username)
          setUsername(data.username)
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
  }

  function logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('username')
    setUsername('')
    setLoggedIn(false)
  }

  return (
    <AuthContext.Provider value={{ loggedIn, username, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
