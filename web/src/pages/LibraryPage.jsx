import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import api from '../api/client'

export default function LibraryPage() {
  const { data: artists = [], isLoading } = useQuery({
    queryKey: ['artists'],
    queryFn: () => api.get('/artists').then((r) => r.data),
  })

  if (isLoading) return <div className="loading">Loading…</div>

  return (
    <div className="page">
      <h2>Artists</h2>
      <ul className="artist-list">
        {artists.map((a) => (
          <li key={a.id}>
            <Link to={`/artists/${a.id}`}>{a.name}</Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
