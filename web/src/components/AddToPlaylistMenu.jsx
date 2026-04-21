import { useEffect, useRef, useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import api from '../api/client'

export default function AddToPlaylistMenu({ trackId }) {
  const [open, setOpen] = useState(false)
  const [added, setAdded] = useState(null)
  const ref = useRef(null)

  const { data: playlists = [] } = useQuery({
    queryKey: ['playlists'],
    queryFn: () => api.get('/playlists').then((r) => r.data),
    enabled: open,
  })

  const addMutation = useMutation({
    mutationFn: (playlistId) =>
      api.post(`/playlists/${playlistId}/tracks`, { track_id: trackId }),
    onSuccess: (_, playlistId) => {
      setAdded(playlistId)
      setTimeout(() => { setOpen(false); setAdded(null) }, 800)
    },
  })

  // Close on outside click
  useEffect(() => {
    if (!open) return
    function handle(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  return (
    <div className="atp-wrap" ref={ref}>
      <button
        className="atp-trigger"
        title="Add to playlist"
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v) }}
      >
        +
      </button>
      {open && (
        <div className="atp-menu">
          {playlists.length === 0 && <div className="atp-empty">No playlists</div>}
          {playlists.map((pl) => (
            <button
              key={pl.id}
              className={`atp-item ${added === pl.id ? 'atp-item--added' : ''}`}
              onClick={() => addMutation.mutate(pl.id)}
              disabled={addMutation.isPending}
            >
              {added === pl.id ? '✓ Added' : pl.title}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
