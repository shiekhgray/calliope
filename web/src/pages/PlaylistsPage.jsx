import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import api from '../api/client'

export default function PlaylistsPage() {
  const qc = useQueryClient()
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
        <ul className="playlist-list">
          {playlists.map((pl) => (
            <li key={pl.id} className="playlist-item">
              <Link to={`/playlists/${pl.id}`}>{pl.title}</Link>
              <button
                className="delete-btn"
                onClick={() => deleteMutation.mutate(pl.id)}
                title="Delete"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
