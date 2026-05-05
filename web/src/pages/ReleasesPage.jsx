import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import api from '../api/client'
import ReleaseCardGenres from '../components/ReleaseCardGenres'

function useRefreshPoller(onDone) {
  const pollRef = useRef(null)

  function startPolling() {
    pollRef.current = setInterval(() => {
      api.get('/discover/status').then((r) => {
        if (!r.data.running) {
          clearInterval(pollRef.current)
          onDone(r.data.last_refreshed)
        }
      })
    }, 2000)
  }

  useEffect(() => () => clearInterval(pollRef.current), [])

  return startPolling
}

export default function ReleasesPage() {
  const qc = useQueryClient()
  const [refreshState, setRefreshState] = useState('idle') // idle | running | done
  const [lastRefreshed, setLastRefreshed] = useState(null)
  const [filterText, setFilterText] = useState('')
  const [sortKey, setSortKey] = useState('artist') // 'artist' | 'newest' | 'oldest'

  const { data: discoveries = [], isLoading } = useQuery({
    queryKey: ['discoveries'],
    queryFn: () => api.get('/discover').then((r) => r.data),
  })

  // Seed last_refreshed from status on mount
  useEffect(() => {
    api.get('/discover/status').then((r) => {
      if (r.data.last_refreshed) setLastRefreshed(r.data.last_refreshed)
      if (r.data.running) {
        setRefreshState('running')
        startPolling()
      }
    })
  }, [])

  const startPolling = useRefreshPoller((ts) => {
    setRefreshState('done')
    setLastRefreshed(ts)
    qc.invalidateQueries({ queryKey: ['discoveries'] })
    setTimeout(() => setRefreshState('idle'), 3000)
  })

  function handleRefresh() {
    api.post('/discover/refresh')
      .then(() => {
        setRefreshState('running')
        startPolling()
      })
      .catch((err) => {
        if (err.response?.status === 409) {
          setRefreshState('running')
          startPolling()
        }
      })
  }

  const dismissMutation = useMutation({
    mutationFn: (id) => api.post(`/discover/${id}/dismiss`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['discoveries'] }),
  })

  const displayed = useMemo(() => {
    let list = [...discoveries]

    if (filterText.trim()) {
      const q = filterText.trim().toLowerCase()
      list = list.filter(
        (d) =>
          d.artist_name.toLowerCase().includes(q) ||
          d.album_title.toLowerCase().includes(q)
      )
    }

    if (sortKey === 'artist') {
      list.sort((a, b) =>
        a.artist_name.localeCompare(b.artist_name) ||
        a.album_title.localeCompare(b.album_title)
      )
    } else if (sortKey === 'newest') {
      list.sort((a, b) => (b.release_date ?? '').localeCompare(a.release_date ?? ''))
    } else {
      list.sort((a, b) => (a.release_date ?? 'zzzz').localeCompare(b.release_date ?? 'zzzz'))
    }

    return list
  }, [discoveries, filterText, sortKey])

  const refreshLabel =
    refreshState === 'running' ? 'Refreshing…' :
    refreshState === 'done'    ? 'Up to date' :
                                 'Refresh'

  const formattedDate = lastRefreshed
    ? new Date(lastRefreshed + 'Z').toLocaleDateString(undefined, {
        month: 'short', day: 'numeric', year: 'numeric',
      })
    : null

  if (isLoading) return <div className="loading">Loading…</div>

  return (
    <div className="page">
      <div className="page-header">
        <h2>Releases</h2>
        <div className="releases-header-right">
          {formattedDate && (
            <span className="releases-last-refreshed">Updated {formattedDate}</span>
          )}
          <button
            onClick={handleRefresh}
            disabled={refreshState === 'running'}
            className={refreshState === 'done' ? 'menu-item-success' : ''}
          >
            {refreshLabel}
          </button>
        </div>
      </div>

      {!lastRefreshed && discoveries.length === 0 && (
        <p className="empty">Hit Refresh to fetch new releases from your artists.</p>
      )}

      {lastRefreshed && discoveries.length === 0 && (
        <p className="empty">You're all caught up — no missing albums found.</p>
      )}

      {discoveries.length > 0 && (
        <div className="releases-controls">
          <input
            className="releases-filter-input"
            type="search"
            placeholder="Filter by artist or album…"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
          />
          <select
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value)}
          >
            <option value="artist">Artist A–Z</option>
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
          </select>
        </div>
      )}

      {filterText.trim() && (
        <p className="releases-count">
          Showing {displayed.length} of {discoveries.length}
        </p>
      )}

      {filterText.trim() && displayed.length === 0 && (
        <p className="empty">No releases match your filter.</p>
      )}

      <div className="releases-grid">
        {displayed.map((d) => (
          <div key={d.id} className="release-card">
            {d.artwork_url ? (
              <img src={d.artwork_url} alt={d.album_title} />
            ) : (
              <div className="release-card-no-art" />
            )}
            <div className="release-card-body">
              <div className="release-card-title">{d.album_title}</div>
              <Link to={`/artists/${d.artist_id}`} className="release-card-artist">
                {d.artist_name}
              </Link>
              {d.release_date && (
                <div className="release-card-year">
                  {d.release_date.slice(0, 4)}
                </div>
              )}
              <ReleaseCardGenres discoveryId={d.id} />
              <button
                className="release-dismiss-btn"
                onClick={() => dismissMutation.mutate(d.id)}
                disabled={dismissMutation.isPending}
                title="Dismiss"
              >
                Dismiss
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
