import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import api from '../api/client'
import { usePlayer } from '../player/PlayerContext'
import { useRegisterFirstTrack } from '../hooks/useSpacebarPlayback'
import AddToPlaylistMenu from '../components/AddToPlaylistMenu'

function fmt(ms) {
  if (!ms) return ''
  const s = Math.round(ms / 1000)
  return `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`
}

export default function PlaylistPage() {
  const { id } = useParams()
  const qc = useQueryClient()
  const { playTrack, currentTrack, isPlaying } = usePlayer()
  const [editingTitle, setEditingTitle] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [localTracks, setLocalTracks] = useState(null)
  const dragIndex = useRef(null)
  const dragOverIndex = useRef(null)

  const { data: playlist, isLoading } = useQuery({
    queryKey: ['playlist', id],
    queryFn: () => api.get(`/playlists/${id}`).then((r) => r.data),
    onSuccess: () => setLocalTracks(null), // reset local order on fresh fetch
  })

  const renameMutation = useMutation({
    mutationFn: (title) => api.put(`/playlists/${id}`, { title }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playlist', id] })
      qc.invalidateQueries({ queryKey: ['playlists'] })
      setEditingTitle(false)
    },
  })

  const removeTrackMutation = useMutation({
    mutationFn: (trackId) => api.delete(`/playlists/${id}/tracks/${trackId}`),
    onSuccess: () => {
      setLocalTracks(null)
      qc.invalidateQueries({ queryKey: ['playlist', id] })
    },
  })

  const reorderMutation = useMutation({
    mutationFn: (trackIds) => api.put(`/playlists/${id}/tracks/reorder`, { track_ids: trackIds }),
    onError: () => {
      setLocalTracks(null)
      qc.invalidateQueries({ queryKey: ['playlist', id] })
    },
  })

  useRegisterFirstTrack(() => {
    const entries = playlist?.entries ?? []
    const first = (localTracks ?? entries.map((e) => e.track))[0]
    return first ?? null
  })

  if (isLoading || !playlist) return <div className="loading">Loading…</div>

  const serverTracks = playlist.entries?.map((e) => ({ ...e.track, entry_id: e.id })) ?? []
  const tracks = localTracks ?? serverTracks

  function handleDragStart(i) {
    dragIndex.current = i
  }

  function handleDragOver(e, i) {
    e.preventDefault()
    dragOverIndex.current = i
  }

  function handleDrop() {
    const from = dragIndex.current
    const to = dragOverIndex.current
    if (from === null || to === null || from === to) return

    const reordered = [...tracks]
    const [moved] = reordered.splice(from, 1)
    reordered.splice(to, 0, moved)

    setLocalTracks(reordered)
    reorderMutation.mutate(reordered.map((t) => t.id))

    dragIndex.current = null
    dragOverIndex.current = null
  }

  function handleDragEnd() {
    dragIndex.current = null
    dragOverIndex.current = null
  }

  return (
    <div className="page">
      <div className="page-header">
        {editingTitle ? (
          <form
            className="inline-form"
            onSubmit={(e) => {
              e.preventDefault()
              if (newTitle.trim()) renameMutation.mutate(newTitle.trim())
            }}
          >
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              autoFocus
            />
            <button type="submit">Save</button>
            <button type="button" onClick={() => setEditingTitle(false)}>Cancel</button>
          </form>
        ) : (
          <>
            <h2>{playlist.title}</h2>
            <button onClick={() => { setNewTitle(playlist.title); setEditingTitle(true) }}>
              Rename
            </button>
          </>
        )}
      </div>

      {tracks.length === 0 ? (
        <p className="empty">No tracks yet.</p>
      ) : (
        <>
          <button
            className="play-all-btn"
            onClick={() => tracks.length && playTrack(tracks[0], tracks)}
          >
            ▶ Play all
          </button>
          <table className="track-table">
            <tbody>
              {tracks.map((track, i) => {
                const active = currentTrack?.id === track.id
                return (
                  <tr
                    key={track.entry_id}
                    className={active ? 'active' : ''}
                    draggable
                    onDragStart={() => handleDragStart(i)}
                    onDragOver={(e) => handleDragOver(e, i)}
                    onDrop={handleDrop}
                    onDragEnd={handleDragEnd}
                  >
                    <td className="track-drag" title="Drag to reorder">⠿</td>
                    <td className="track-num">{i + 1}</td>
                    <td className="track-name">
                      <button
                        className="track-play-btn"
                        onClick={() => playTrack(track, tracks)}
                      >
                        {active && isPlaying ? '⏸' : '▶'}
                      </button>
                      {track.title}
                    </td>
                    <td className="track-duration">{fmt(track.duration_ms)}</td>
                    <td className="track-bitrate">{track.bitrate_kbps ? `${track.bitrate_kbps} kbps` : ''}</td>
                    <td className="track-actions"><AddToPlaylistMenu trackId={track.id} /></td>
                    <td>
                      <button
                        className="delete-btn"
                        onClick={() => removeTrackMutation.mutate(track.id)}
                        title="Remove"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
