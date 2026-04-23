import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import api from '../api/client'

export default function CompilationsPage() {
  const { data: compilations = [], isLoading } = useQuery({
    queryKey: ['compilations'],
    queryFn: () => api.get('/compilations').then((r) => r.data),
  })

  if (isLoading) return <div className="loading">Loading…</div>

  return (
    <div className="page">
      <div className="page-header">
        <h2>Compilations</h2>
      </div>

      {compilations.length === 0 ? (
        <p className="empty">No compilation albums found.</p>
      ) : (
        <div className="album-grid">
          {compilations.map((album) => (
            <Link key={album.id} to={`/albums/${album.id}`} className="album-card">
              {album.cover_art_path ? (
                <img src={`/calliope/api/albums/${album.id}/art`} alt={album.title} />
              ) : (
                <div className="album-art-placeholder">♪</div>
              )}
              <div className="album-info">
                <span className="album-title">{album.title}</span>
                <span className="album-year">
                  {[album.year, `${album.track_count} tracks`].filter(Boolean).join(' · ')}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
