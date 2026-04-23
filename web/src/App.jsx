import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import LoginPage from './auth/LoginPage'
import Layout from './components/Layout'
import LibraryPage from './pages/LibraryPage'
import ArtistPage from './pages/ArtistPage'
import AlbumPage from './pages/AlbumPage'
import SearchPage from './pages/SearchPage'
import PlaylistsPage from './pages/PlaylistsPage'
import PlaylistPage from './pages/PlaylistPage'
import ReleasesPage from './pages/ReleasesPage'
import NowPlayingPage from './pages/NowPlayingPage'
import CompilationsPage from './pages/CompilationsPage'
import ImportPage from './pages/ImportPage'

function RequireAuth({ children }) {
  const { loggedIn } = useAuth()
  const location = useLocation()
  if (!loggedIn) {
    const redirect = location.pathname + location.search
    return <Navigate to={`/login?redirect=${encodeURIComponent(redirect)}`} replace />
  }
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={<RequireAuth><Layout /></RequireAuth>}
      >
        <Route index element={<LibraryPage />} />
        <Route path="artists/:id" element={<ArtistPage />} />
        <Route path="albums/:id" element={<AlbumPage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="playlists" element={<PlaylistsPage />} />
        <Route path="playlists/:id" element={<PlaylistPage />} />
        <Route path="releases" element={<ReleasesPage />} />
        <Route path="compilations" element={<CompilationsPage />} />
        <Route path="now-playing" element={<NowPlayingPage />} />
        <Route path="import" element={<ImportPage />} />
      </Route>
    </Routes>
  )
}
