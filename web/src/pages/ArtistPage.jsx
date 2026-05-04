import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import api from '../api/client'
import { usePlayer } from '../player/PlayerContext'
import { useAuth } from '../auth/AuthContext'
import { useRegisterFirstTrack } from '../hooks/useSpacebarPlayback'

function fmt(ms) {
  if (!ms) return ''
  const s = Math.round(ms / 1000)
  return `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`
}

export default function ArtistPage() {
  const { id } = useParams()
  const { playTrack, currentTrack, isPlaying } = usePlayer()
  const { loggedIn } = useAuth()
  const qc = useQueryClient()

  const { data: albums = [], isLoading } = useQuery({
    queryKey: ['artist-albums', id],
    queryFn: () => api.get(`/artists/${id}/albums`).then((r) => r.data),
  })

  const { data: topTracks = [] } = useQuery({
    queryKey: ['artist-top-tracks', id],
    queryFn: () => api.get(`/artists/${id}/top-tracks?limit=10`).then((r) => r.data),
  })

  const { data: compilations = [] } = useQuery({
    queryKey: ['artist-compilations', id],
    queryFn: () => api.get(`/artists/${id}/compilations`).then((r) => r.data),
  })

  const { data: singles = [] } = useQuery({
    queryKey: ['artist-singles', id],
    queryFn: () => api.get(`/artists/${id}/singles`).then((r) => r.data),
  })

  const { data: missingReleases = [] } = useQuery({
    queryKey: ['discoveries', 'artist', id],
    queryFn: () => api.get('/discover', { params: { artist_id: id } }).then((r) => r.data),
  })

  const dismissMutation = useMutation({
    mutationFn: (discoveryId) => api.post(`/discover/${discoveryId}/dismiss`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['discoveries', 'artist', id] })
      qc.invalidateQueries({ queryKey: ['discoveries'] })
    },
  })

  useRegisterFirstTrack(() => topTracks[0] ?? null)

  if (isLoading) return <div className="loading">Loading…</div>

  const artistName = albums[0]?.artist_name ?? 'Artist'

  return (
    <div className="page">
      <h2>{artistName}</h2>

      <section className="top-tracks">
        <h3 className="section-heading">Top Tracks</h3>
        <table className="track-table">
            <tbody>
              {topTracks.map((track, i) => {
                const active = currentTrack?.id === track.id
                return (
                  <tr
                    key={track.id}
                    className={active ? 'active' : ''}
                    onDoubleClick={() => playTrack(track, topTracks)}
                  >
                    <td className="track-num">{i + 1}</td>
                    <td className="track-name">
                      <button className="track-play-btn" onClick={() => playTrack(track, topTracks)}>
                        {active && isPlaying ? '⏸' : '▶'}
                      </button>
                      {track.title}
                    </td>
                    <td className="track-meta-dim">
                      <Link to={`/albums/${track.album_id}`}>{track.album_title}</Link>
                    </td>
                    <td className="track-duration">{fmt(track.duration_ms)}</td>
                    <td className="track-play-count">{track.play_count} plays</td>
                  </tr>
                )
              })}
          </tbody>
        </table>
      </section>

      <h3 className="section-heading">Albums</h3>
      <div className="album-grid">
        {albums.map((album) => (
          <Link key={album.id} to={`/albums/${album.id}`} className="album-card">
            {album.cover_art_path ? (
              <img src={`/calliope/api/albums/${album.id}/art`} alt={album.title} />
            ) : (
              <div className="album-art-placeholder">♪</div>
            )}
            <div className="album-info">
              <span className="album-title">{album.title}</span>
              {album.year && <span className="album-year">{album.year}</span>}
            </div>
          </Link>
        ))}
      </div>

      {singles.length > 0 && (
        <section style={{ marginTop: '36px' }}>
          <h3 className="section-heading">Singles &amp; EPs</h3>
          <div className="album-grid">
            {singles.map((single) => {
              const isThisPlaying = currentTrack?.id === single.first_track?.id && isPlaying
              return (
                <div key={single.id} className="album-card">
                  <div className="single-art-wrap">
                    <Link to={`/albums/${single.id}`} className="single-art-link">
                      {single.cover_art_path ? (
                        <img src={`/calliope/api/albums/${single.id}/art`} alt={single.title} />
                      ) : (
                        <div className="album-art-placeholder">♪</div>
                      )}
                    </Link>
                    {single.first_track && (
                      <button
                        className="single-play-btn"
                        onClick={() => playTrack(single.first_track, [single.first_track])}
                      >
                        {isThisPlaying ? '⏸' : '▶'}
                      </button>
                    )}
                  </div>
                  <Link to={`/albums/${single.id}`} className="album-info single-info-link">
                    <span className="album-title">{single.title}</span>
                    <div className="album-year-type">
                      {single.year && <span className="album-year">{single.year}</span>}
                      <span className="album-type-badge">
                        {single.album_type === 'ep' ? 'EP' : 'Single'}
                      </span>
                    </div>
                  </Link>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {compilations.length > 0 && (
        <section style={{ marginTop: '36px' }}>
          <h3 className="section-heading">Appears On</h3>
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
                  {album.year && <span className="album-year">{album.year}</span>}
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {missingReleases.length > 0 && (
        <section className="missing-releases">
          <h3 className="section-heading">Missing Releases</h3>
          <div className="releases-grid">
            {missingReleases.map((d) => (
              <div key={d.id} className="release-card">
                {d.artwork_url
                  ? <img src={d.artwork_url} alt={d.album_title} />
                  : <div className="release-card-no-art" />}
                <div className="release-card-body">
                  <div className="release-card-title">{d.album_title}</div>
                  {d.release_date && (
                    <div className="release-card-year">{d.release_date.slice(0, 4)}</div>
                  )}
                  {loggedIn && (
                    <button
                      className="release-dismiss-btn"
                      onClick={() => dismissMutation.mutate(d.id)}
                      disabled={dismissMutation.isPending}
                    >
                      Dismiss
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
