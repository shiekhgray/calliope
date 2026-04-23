import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import api from '../api/client'
import { usePlayer } from '../player/PlayerContext'
import { useRegisterFirstTrack } from '../hooks/useSpacebarPlayback'
import AddToPlaylistMenu from '../components/AddToPlaylistMenu'

function slugify(str) {
  return String(str).toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
}

function ShareButton({ track, albumId, artistName, albumTitle }) {
  const [copied, setCopied] = useState(false)

  function handleShare(e) {
    e.stopPropagation()
    const note = slugify(artistName) + '_' + slugify(albumTitle)
    const url = `${window.location.origin}/calliope/albums/${albumId}?play=${track.id}&note=${note}`
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <button className="track-share-btn" onClick={handleShare} title="Copy link">
      {copied ? <span className="track-share-tooltip">Copied!</span> : '🔗'}
    </button>
  )
}

function fmt(ms) {
  if (!ms) return ''
  const s = Math.round(ms / 1000)
  return `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`
}

export default function AlbumPage() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const playTrackId = searchParams.get('play') ? Number(searchParams.get('play')) : null
  const { playTrack, currentTrack, isPlaying } = usePlayer()
  const queryClient = useQueryClient()
  const fileInputRef = useRef(null)
  const highlightRef = useRef(null)
  const [artVersion, setArtVersion] = useState(0)
  const [artUploading, setArtUploading] = useState(false)
  const [autoPlayAttempted, setAutoPlayAttempted] = useState(false)

  function handleArtUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    setArtUploading(true)
    api.put(`/albums/${id}/art`, form)
      .then(() => {
        setArtVersion((v) => v + 1)
        queryClient.invalidateQueries({ queryKey: ['album', id] })
      })
      .finally(() => {
        setArtUploading(false)
        e.target.value = ''
      })
  }

  const { data: album, isLoading } = useQuery({
    queryKey: ['album', id],
    queryFn: () => api.get(`/albums/${id}`).then((r) => r.data),
  })

  function enrichedTrack(t) {
    return { ...t, album_title: album?.title, album_id: album?.id, artist_id: album?.artist_id, artist_name: album?.artist_name }
  }

  useRegisterFirstTrack(() => {
    const t = (album?.tracks ?? [])[0]
    if (!t || !album) return null
    return enrichedTrack(t)
  })

  useEffect(() => {
    if (!album || !playTrackId || autoPlayAttempted) return
    const track = (album.tracks ?? []).find((t) => t.id === playTrackId)
    if (!track) return
    setAutoPlayAttempted(true)
    setTimeout(() => highlightRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 100)
    playTrack(enrichedTrack(track), (album.tracks ?? []).map(enrichedTrack))
  }, [album, playTrackId])

  if (isLoading || !album) return <div className="loading">Loading…</div>

  const tracks = album.tracks ?? []
  const isCompilation = tracks.some((t) => t.track_artist != null)

  function handlePlay(track) {
    playTrack(enrichedTrack(track), tracks.map(enrichedTrack))
  }

  return (
    <div className="page album-page">
      <div className="album-header">
        <div className="album-art-upload-wrap" onClick={() => fileInputRef.current?.click()}>
          {album.cover_art_path ? (
            <img
              className="album-art-large"
              src={`/calliope/api/albums/${id}/art?v=${artVersion}`}
              alt={album.title}
            />
          ) : (
            <div className="album-art-large album-art-placeholder">♪</div>
          )}
          <div className="album-art-upload-overlay">
            {artUploading ? 'Uploading…' : '📷 Change art'}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={handleArtUpload}
          />
        </div>
        <div className="album-header-info">
          <h2>{album.title}</h2>
          <p className="album-artist">{album.artist_name}</p>
          {album.year && <p className="album-year">{album.year}</p>}
          <button
            className="play-all-btn"
            onClick={() => tracks.length && handlePlay(tracks[0])}
          >
            ▶ Play all
          </button>
        </div>
      </div>

      <table className="track-table">
        <tbody>
          {tracks.map((track) => {
            const active = currentTrack?.id === track.id
            const highlighted = track.id === playTrackId
            return (
              <tr
                key={track.id}
                ref={highlighted ? highlightRef : null}
                className={[active ? 'active' : '', highlighted ? 'track-row--highlighted' : ''].filter(Boolean).join(' ')}
                onDoubleClick={() => handlePlay(track)}
              >
                <td className="track-num">{track.track_number ?? '—'}</td>
                {isCompilation && (
                  <td className="track-meta-dim">
                    {track.track_artist_id
                      ? <Link to={`/artists/${track.track_artist_id}`}>{track.track_artist}</Link>
                      : track.track_artist}
                  </td>
                )}
                <td className="track-name">
                  <button className="track-play-btn" onClick={() => handlePlay(track)}>
                    {active && isPlaying ? '⏸' : '▶'}
                  </button>
                  {track.title}
                  {highlighted && !active && (
                    <button className="track-highlight-play-btn" onClick={() => handlePlay(track)}>▶ Play</button>
                  )}
                </td>
                <td className="track-duration">{fmt(track.duration_ms)}</td>
                <td className="track-bitrate">{track.bitrate_kbps ? `${track.bitrate_kbps} kbps` : ''}</td>
                <td className="track-play-count">{track.play_count > 0 ? `${track.play_count} plays` : ''}</td>
                <td className="track-actions">
                  <div className="track-actions-group">
                    <AddToPlaylistMenu trackId={track.id} />
                    <ShareButton
                      track={track}
                      albumId={id}
                      artistName={album.artist_name}
                      albumTitle={album.title}
                    />
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
