import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, Link, useNavigate } from 'react-router-dom'
import api from '../api/client'
import { usePlayer } from '../player/PlayerContext'
import { useAuth } from '../auth/AuthContext'
import { useRegisterFirstTrack } from '../hooks/useSpacebarPlayback'
import AddToPlaylistMenu from '../components/AddToPlaylistMenu'

const SKELETON_COUNT = 10

function fmt(ms) {
  if (!ms) return ''
  const s = Math.round(ms / 1000)
  return `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`
}

export default function PlaylistPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { playTrack, currentTrack, isPlaying } = usePlayer()
  const { userId } = useAuth()
  const [editingTitle, setEditingTitle] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [localTracks, setLocalTracks] = useState(null)
  const dragIndex = useRef(null)
  const dragOverIndex = useRef(null)

  // Permissions panel state
  const [showPermissions, setShowPermissions] = useState(false)
  const [viewMode, setViewMode] = useState('everyone')
  const [editMode, setEditMode] = useState('owner')
  const [viewerIds, setViewerIds] = useState([])
  const [editorIds, setEditorIds] = useState([])

  const { data: playlist, isLoading } = useQuery({
    queryKey: ['playlist', id],
    queryFn: () => api.get(`/playlists/${id}`).then((r) => r.data),
    onSuccess: () => setLocalTracks(null), // reset local order on fresh fetch
  })

  const { data: users = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.get('/users').then((r) => r.data),
  })

  const renameMutation = useMutation({
    mutationFn: (title) => api.put(`/playlists/${id}`, { title }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playlist', id] })
      qc.invalidateQueries({ queryKey: ['playlists'] })
      setEditingTitle(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.delete(`/playlists/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playlists'] })
      navigate('/playlists')
    },
  })

  const permissionsMutation = useMutation({
    mutationFn: (data) => api.put(`/playlists/${id}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playlist', id] })
      qc.invalidateQueries({ queryKey: ['playlists'] })
      setShowPermissions(false)
    },
  })

  const removeTrackMutation = useMutation({
    mutationFn: (trackId) => api.delete(`/playlists/${id}/tracks/${trackId}`),
    onSuccess: () => {
      setLocalTracks(null)
      qc.invalidateQueries({ queryKey: ['playlist', id] })
      qc.invalidateQueries({ queryKey: ['playlist-similar', id] })
    },
  })

  const addSimilarTrackMutation = useMutation({
    mutationFn: (trackId) => api.post(`/playlists/${id}/tracks`, { track_id: trackId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['playlist', id] })
      qc.invalidateQueries({ queryKey: ['playlist-similar', id] })
    },
  })

  const reorderMutation = useMutation({
    mutationFn: (trackIds) => api.put(`/playlists/${id}/tracks/reorder`, { track_ids: trackIds }),
    onError: () => {
      setLocalTracks(null)
      qc.invalidateQueries({ queryKey: ['playlist', id] })
    },
  })

  const { data: similarTracks = [], isFetching: similarFetching } = useQuery({
    queryKey: ['playlist-similar', id],
    queryFn: () => api.get(`/playlists/${id}/similar`).then((r) => r.data),
    enabled: (playlist?.entries?.length ?? 0) > 0,
    staleTime: 30_000,
    retry: 1,
  })

  useRegisterFirstTrack(() => {
    const entries = playlist?.entries ?? []
    const first = (localTracks ?? entries.map((e) => e.track))[0]
    return first ?? null
  })

  if (isLoading || !playlist) return <div className="loading">Loading…</div>

  const serverTracks = playlist.entries?.map((e) => ({ ...e.track, entry_id: e.id })) ?? []
  const tracks = localTracks ?? serverTracks

  const isOwner = playlist.owner_id === userId
  const canEdit =
    isOwner ||
    playlist.edit_mode === 'everyone' ||
    (playlist.edit_mode === 'users' && playlist.editor_ids?.includes(userId))

  const ownerUser = users.find((u) => u.id === playlist.owner_id)
  const otherUsers = users.filter((u) => u.id !== playlist.owner_id)

  function openPermissions() {
    setViewMode(playlist.view_mode ?? 'everyone')
    setEditMode(playlist.edit_mode ?? 'owner')
    setViewerIds(playlist.viewer_ids ?? [])
    setEditorIds(playlist.editor_ids ?? [])
    setShowPermissions(true)
  }

  function toggleUserId(setList, uid) {
    setList((prev) =>
      prev.includes(uid) ? prev.filter((x) => x !== uid) : [...prev, uid]
    )
  }

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
            <div>
              <h2>{playlist.title}</h2>
              {!isOwner && ownerUser && (
                <div className="playlist-owner-subtitle">by {ownerUser.username}</div>
              )}
            </div>
            {canEdit && (
              <button onClick={() => { setNewTitle(playlist.title); setEditingTitle(true) }}>
                Rename
              </button>
            )}
            {isOwner && (
              <button
                className="gear-btn"
                title="Permissions"
                onClick={() => showPermissions ? setShowPermissions(false) : openPermissions()}
              >
                ⚙
              </button>
            )}
            {isOwner && (
              <button
                className="delete-btn"
                title="Delete playlist"
                onClick={() => {
                  if (window.confirm(`Delete "${playlist.title}"?`)) deleteMutation.mutate()
                }}
              >
                ✕
              </button>
            )}
          </>
        )}
      </div>

      {showPermissions && (
        <div className="permissions-panel">
          <div className="permissions-section">
            <div className="permissions-section-title">Who can view</div>
            <div className="permissions-radio-group">
              {[['owner', 'Only me'], ['users', 'Specific users'], ['everyone', 'Everyone']].map(([val, label]) => (
                <label key={val}>
                  <input
                    type="radio"
                    name="view_mode"
                    value={val}
                    checked={viewMode === val}
                    onChange={() => setViewMode(val)}
                  />
                  {label}
                </label>
              ))}
            </div>
            {viewMode === 'users' && otherUsers.length > 0 && (
              <div className="permissions-user-list">
                {otherUsers.map((u) => (
                  <label key={u.id}>
                    <input
                      type="checkbox"
                      checked={viewerIds.includes(u.id)}
                      onChange={() => toggleUserId(setViewerIds, u.id)}
                    />
                    {u.username}
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="permissions-section">
            <div className="permissions-section-title">Who can edit</div>
            <div className="permissions-radio-group">
              {[['owner', 'Only me'], ['users', 'Specific users'], ['everyone', 'Everyone']].map(([val, label]) => (
                <label key={val}>
                  <input
                    type="radio"
                    name="edit_mode"
                    value={val}
                    checked={editMode === val}
                    onChange={() => setEditMode(val)}
                  />
                  {label}
                </label>
              ))}
            </div>
            {editMode === 'users' && otherUsers.length > 0 && (
              <div className="permissions-user-list">
                {otherUsers.map((u) => (
                  <label key={u.id}>
                    <input
                      type="checkbox"
                      checked={editorIds.includes(u.id)}
                      onChange={() => toggleUserId(setEditorIds, u.id)}
                    />
                    {u.username}
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="permissions-save-row">
            <button
              className="btn-primary"
              style={{ background: 'var(--accent)', border: '1px solid var(--accent)', color: '#fff', borderRadius: '7px', padding: '8px 18px', fontSize: '0.9rem' }}
              disabled={permissionsMutation.isPending}
              onClick={() =>
                permissionsMutation.mutate({ view_mode: viewMode, edit_mode: editMode, viewer_ids: viewerIds, editor_ids: editorIds })
              }
            >
              Save
            </button>
          </div>
        </div>
      )}

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
                    draggable={canEdit}
                    onDragStart={canEdit ? () => handleDragStart(i) : undefined}
                    onDragOver={canEdit ? (e) => handleDragOver(e, i) : undefined}
                    onDrop={canEdit ? handleDrop : undefined}
                    onDragEnd={canEdit ? handleDragEnd : undefined}
                  >
                    {canEdit && <td className="track-drag" title="Drag to reorder">⠿</td>}
                    {!canEdit && <td />}
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
                    <td className="track-meta-dim">
                      {track.artist_id && (
                        <Link className="player-link" to={`/artists/${track.artist_id}`}>{track.artist_name}</Link>
                      )}
                      {track.artist_id && track.album_id && <> · </>}
                      {track.album_id && (
                        <Link className="player-link" to={`/albums/${track.album_id}`}>{track.album_title}</Link>
                      )}
                    </td>
                    <td className="track-duration">{fmt(track.duration_ms)}</td>
                    <td className="track-bitrate">{track.bitrate_kbps ? `${track.bitrate_kbps} kbps` : ''}</td>
                    <td className="track-actions"><AddToPlaylistMenu trackId={track.id} /></td>
                    <td>
                      {canEdit && (
                        <button
                          className="delete-btn"
                          onClick={() => removeTrackMutation.mutate(track.id)}
                          title="Remove"
                        >
                          ✕
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </>
      )}

      {/* ── Similar Tracks ── */}
      {(similarFetching || similarTracks.length > 0) && tracks.length > 0 && (
        <div className="similar-tracks-section">
          <div className="section-heading">Similar Tracks</div>
          <table className="track-table">
            <tbody>
              {similarFetching && similarTracks.length === 0
                ? Array.from({ length: SKELETON_COUNT }).map((_, i) => (
                    <tr key={`skel-${i}`} className="similar-track-skeleton">
                      <td className="track-name">
                        <span className="track-play-btn" />
                        <span className="similar-skeleton-title" />
                      </td>
                      <td className="track-meta-dim">
                        <span className="similar-skeleton-meta" />
                      </td>
                      <td className="similar-track-add-cell" />
                    </tr>
                  ))
                : similarTracks.map((track) => {
                    const active = currentTrack?.id === track.id
                    return (
                      <tr key={track.id} className={active ? 'active' : ''}>
                        <td className="track-name">
                          <button
                            className="track-play-btn"
                            style={{ color: 'var(--accent)' }}
                            onClick={() => playTrack(track, [track])}
                            title="Play"
                          >
                            {active && isPlaying ? '⏸' : '▶'}
                          </button>
                          {track.title}
                        </td>
                        <td className="track-meta-dim">
                          {track.artist_name}
                          {track.album_title && (
                            <> · {track.album_title}</>
                          )}
                        </td>
                        <td className="similar-track-add-cell">
                          <button
                            className="similar-add-btn"
                            onClick={() => addSimilarTrackMutation.mutate(track.id)}
                            title="Add to playlist"
                          >
                            + Add
                          </button>
                        </td>
                      </tr>
                    )
                  })
              }
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
