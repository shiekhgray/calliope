import { useState } from 'react'
import api from '../api/client'

// Per-card genre fetch for discovery cards — read-only, no persistence
export default function ReleaseCardGenres({ discoveryId }) {
  const [genres, setGenres] = useState(null) // null = not fetched, [] = empty, [...] = results
  const [loading, setLoading] = useState(false)
  const [visible, setVisible] = useState(true)

  async function handleFetch() {
    if (genres !== null) {
      setVisible((v) => !v)
      return
    }
    setLoading(true)
    try {
      const r = await api.get(`/discover/${discoveryId}/genres/fetch`)
      setGenres(r.data)
      setVisible(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <button
        style={{ fontSize: '0.75rem', color: 'var(--accent)', background: 'none', border: 'none', cursor: 'pointer', padding: '4px 0' }}
        onClick={handleFetch}
        disabled={loading}
      >
        {loading ? 'Fetching…' : genres !== null ? (visible ? 'Hide genres' : 'Show genres') : 'Genres'}
      </button>
      {genres !== null && visible && (
        <div className="genre-chips" style={{ marginTop: '4px' }}>
          {genres.length === 0
            ? <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>No genres found</span>
            : genres.map((g) => (
                <span key={g.name} className="genre-chip" style={{ fontSize: '0.75rem', padding: '2px 8px' }}>
                  {g.name}
                </span>
              ))
          }
        </div>
      )}
    </div>
  )
}
