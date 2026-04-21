import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import PlayerBar from './PlayerBar'
import ChangePasswordModal from './ChangePasswordModal'
import api from '../api/client'

function UserMenu({ username, onLogout }) {
  const [open, setOpen] = useState(false)
  const [changingPassword, setChangingPassword] = useState(false)
  const [scanState, setScanState] = useState('idle') // idle | scanning | done
  const ref = useRef(null)
  const pollRef = useRef(null)

  useEffect(() => {
    if (!open) return
    function handle(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  // Clean up poll on unmount
  useEffect(() => () => clearInterval(pollRef.current), [])

  function startScan() {
    api.post('/scanner/trigger').then(() => {
      setScanState('scanning')
      pollRef.current = setInterval(() => {
        api.get('/scanner/status').then((r) => {
          if (!r.data.running) {
            clearInterval(pollRef.current)
            setScanState('done')
            setTimeout(() => setScanState('idle'), 3000)
          }
        })
      }, 2000)
    }).catch((err) => {
      if (err.response?.status === 409) {
        setScanState('scanning')
      }
    })
  }

  const scanLabel =
    scanState === 'scanning' ? 'Scanning…' :
    scanState === 'done'     ? 'Scan complete' :
                               'Rescan library'

  return (
    <>
      <div className="user-menu-wrap" ref={ref}>
        <button className="user-menu-btn" onClick={() => setOpen((v) => !v)}>
          {username} <span className="user-menu-caret">▾</span>
        </button>
        {open && (
          <div className="user-menu-popup">
            <button
              onClick={startScan}
              disabled={scanState === 'scanning'}
              className={scanState === 'done' ? 'menu-item-success' : ''}
            >
              {scanLabel}
            </button>
            <button onClick={() => { setOpen(false); setChangingPassword(true) }}>Change password</button>
            <button onClick={onLogout}>Sign out</button>
          </div>
        )}
      </div>
      {changingPassword && <ChangePasswordModal onClose={() => setChangingPassword(false)} />}
    </>
  )
}

export default function Layout() {
  const { logout, username } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="app-shell">
      <nav className="top-nav">
        <span className="nav-brand">Calliope</span>
        <div className="nav-links">
          <NavLink to="/">Library</NavLink>
          <NavLink to="/search">Search</NavLink>
          <NavLink to="/playlists">Playlists</NavLink>
          <NavLink to="/releases">Releases</NavLink>
        </div>
        <UserMenu username={username} onLogout={handleLogout} />
      </nav>

      <main className="main-content">
        <Outlet />
      </main>

      <PlayerBar />
    </div>
  )
}
