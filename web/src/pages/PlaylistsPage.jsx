import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'

function PlaylistCard({ pl, userId, onDelete }) {
  return (
    <Link className="playlist-card" to={`/playlists/${pl.id}`}>
      <div className="playlist-card-art">
        {pl.art_tracks.map((at) => (
          <img
            key={at.track_id}
            src={`/calliope/api/albums/${at.album_id}/art`}
            alt=""
            onError={(e) => { e.currentTarget.style.display = 'none' }}
          />
        ))}
      </div>
      <div className="playlist-card-text">
        <div className="playlist-card-title">{pl.title}</div>
        {pl.preview_tracks.length > 0 && (
          <div className="playlist-card-tracks">
            {pl.preview_tracks.join(' · ')}
          </div>
        )}
        {pl.top_genres.length > 0 && (
          <div className="playlist-card-genres">
            {pl.top_genres.map((g) => (
              <span key={g} className="genre-chip">{g}</span>
            ))}
          </div>
        )}
      </div>
      {pl.owner_id === userId && (
        <button
          className="playlist-card-delete"
          title="Delete"
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDelete(pl.id) }}
        >
          ✕
        </button>
      )}
    </Link>
  )
}

export default function PlaylistsPage() {
  const qc = useQueryClient()
  const { userId } = useAuth()
  const [newTitle, setNewTitle] = useState('')
  const [creating, setCreating] = useState(false)

  const { data: playlists = [], isLoading } = useQuery({
    queryKey: ['playlists'],
    queryFn: () => api.get('/playlists').then((r) => r.data),
  })

  const createMutation = useMutation({
    mutationFn: (title) => api.post('/playlists', { title }).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playlists'] })
      setNewTitle('')
      setCreating(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => api.delete(`/playlists/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['playlists'] }),
  })

  if (isLoading) return <div className="loading">Loading…</div>

  return (
    <div className="page">
      <div className="page-header">
        <h2>Playlists</h2>
        <button onClick={() => setCreating(true)}>+ New playlist</button>
      </div>

      {creating && (
        <form
          className="inline-form"
          onSubmit={(e) => {
            e.preventDefault()
            if (newTitle.trim()) createMutation.mutate(newTitle.trim())
          }}
        >
          <input
            type="text"
            placeholder="Playlist name"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            autoFocus
          />
          <button type="submit" disabled={createMutation.isPending}>Create</button>
          <button type="button" onClick={() => setCreating(false)}>Cancel</button>
        </form>
      )}

      {playlists.length === 0 ? (
        <p className="empty">No playlists yet.</p>
      ) : (
        <div className="playlist-cards">
          {playlists.map((pl) => (
            <PlaylistCard
              key={pl.id}
              pl={pl}
              userId={userId}
              onDelete={(id) => deleteMutation.mutate(id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
