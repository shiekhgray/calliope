import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { usePlayer } from '../player/PlayerContext'
import AddToPlaylistMenu from '../components/AddToPlaylistMenu'

function SearchHistory({ onPlayTrack }) {
  const { loggedIn } = useAuth()
  const { data: history } = useQuery({
    queryKey: ['search-history'],
    queryFn: () => api.get('/search/history').then((r) => r.data),
    enabled: !!loggedIn,
  })

  if (!loggedIn || !history?.length) return null

  return (
    <div className="search-history-section">
      <div className="search-history-label">Recent</div>
      <div className="search-history-grid">
        {history.map((entry) => {
          if (entry.entity_type === 'artist') {
            return (
              <Link
                key={`artist-${entry.entity_id}`}
                to={`/artists/${entry.entity_id}`}
                className="search-history-chip"
              >
                {entry.name}
              </Link>
            )
          }
          if (entry.entity_type === 'album') {
            return (
              <Link
                key={`album-${entry.entity_id}`}
                to={`/albums/${entry.entity_id}`}
                className="search-history-chip"
              >
                {entry.artist_name} — {entry.name}
              </Link>
            )
          }
          if (entry.entity_type === 'track') {
            return (
              <button
                key={`track-${entry.entity_id}`}
                className="search-history-chip"
                onClick={() => onPlayTrack(entry)}
              >
                {entry.artist_name} — {entry.name}
              </button>
            )
          }
          return null
        })}
      </div>
    </div>
  )
}

export default function SearchPage() {
  const [q, setQ] = useState('')
  const [submitted, setSubmitted] = useState('')
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { playTrack } = usePlayer()

  const { data, isLoading } = useQuery({
    queryKey: ['search', submitted],
    queryFn: () => api.get('/search', { params: { q: submitted } }).then((r) => r.data),
    enabled: submitted.length > 0,
  })

  function handleSubmit(e) {
    e.preventDefault()
    setSubmitted(q.trim())
  }

  function recordHistory(entity_type, entity_id) {
    api.post('/search/history', { entity_type, entity_id }).catch(() => {})
    queryClient.invalidateQueries({ queryKey: ['search-history'] })
  }

  function handleArtistClick(artist) {
    recordHistory('artist', artist.id)
    navigate(`/artists/${artist.id}`)
  }

  function handleAlbumClick(album) {
    recordHistory('album', album.id)
    navigate(`/albums/${album.id}`)
  }

  function handleTrackPlay(track) {
    recordHistory('track', track.id)
    playTrack(track)
  }

  function handleHistoryTrackPlay(entry) {
    // entry from history has album_id, album_title, artist_name — enough for playTrack
    playTrack({
      id: entry.entity_id,
      title: entry.name,
      album_id: entry.album_id,
      album_title: entry.album_title,
      artist_name: entry.artist_name,
    })
    navigate(`/albums/${entry.album_id}`)
  }

  return (
    <div className="page">
      <h2>Search</h2>

      <SearchHistory onPlayTrack={handleHistoryTrackPlay} />

      <form onSubmit={handleSubmit} className="search-form">
        <input
          type="search"
          placeholder="Artists, albums, tracks…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          autoFocus
        />
        <button type="submit">Search</button>
      </form>

      {isLoading && <div className="loading">Searching…</div>}

      {data && (
        <div className="search-results">
          {data.artists?.length > 0 && (
            <section>
              <h3>Artists</h3>
              <ul className="artist-list">
                {data.artists.map((a) => (
                  <li key={a.id}>
                    <a href="#" onClick={(e) => { e.preventDefault(); handleArtistClick(a) }}>{a.name}</a>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {data.albums?.length > 0 && (
            <section>
              <h3>Albums</h3>
              <div className="album-grid">
                {data.albums.map((album) => (
                  <div key={album.id} className="album-card">
                    <a href="#" onClick={(e) => { e.preventDefault(); handleAlbumClick(album) }}>
                      {album.cover_art_path ? (
                        <img src={`/calliope/api/albums/${album.id}/art`} alt={album.title} />
                      ) : (
                        <div className="album-art-placeholder">♪</div>
                      )}
                    </a>
                    <div className="album-info">
                      <a href="#" className="album-title" onClick={(e) => { e.preventDefault(); handleAlbumClick(album) }}>{album.title}</a>
                      <Link to={`/artists/${album.artist_id}`} className="album-artist">{album.artist_name}</Link>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {data.tracks?.length > 0 && (
            <section>
              <h3>Tracks</h3>
              <ul className="track-result-list">
                {data.tracks.map((t) => (
                  <li key={t.id}>
                    <button onClick={() => handleTrackPlay(t)}>▶</button>
                    <span className="track-result-info">
                      <span className="track-result-title">{t.title}</span>
                      <span className="track-result-meta">
                        <Link to={`/artists/${t.artist_id}`}>{t.artist_name}</Link>
                        {' — '}
                        <Link to={`/albums/${t.album_id}`}>{t.album_title}</Link>
                      </span>
                    </span>
                    <AddToPlaylistMenu trackId={t.id} />
                  </li>
                ))}
              </ul>
            </section>
          )}

          {data.artists?.length === 0 && data.albums?.length === 0 && data.tracks?.length === 0 && (
            <p className="no-results">No results for "{submitted}"</p>
          )}
        </div>
      )}
    </div>
  )
}
