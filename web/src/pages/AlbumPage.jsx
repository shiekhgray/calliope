import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api/client'
import { usePlayer } from '../player/PlayerContext'
import AddToPlaylistMenu from '../components/AddToPlaylistMenu'

function fmt(ms) {
  if (!ms) return ''
  const s = Math.round(ms / 1000)
  return `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`
}

export default function AlbumPage() {
  const { id } = useParams()
  const { playTrack, currentTrack, isPlaying } = usePlayer()
  const queryClient = useQueryClient()
  const fileInputRef = useRef(null)
  const [artVersion, setArtVersion] = useState(0)
  const [artUploading, setArtUploading] = useState(false)

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

  if (isLoading || !album) return <div className="loading">Loading…</div>

  const tracks = album.tracks ?? []

  function enrichedTrack(t) {
    return { ...t, album_title: album.title, album_id: album.id, artist_id: album.artist_id, artist_name: album.artist_name }
  }

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
            return (
              <tr
                key={track.id}
                className={active ? 'active' : ''}
                onDoubleClick={() => handlePlay(track)}
              >
                <td className="track-num">{track.track_number ?? '—'}</td>
                <td className="track-name">
                  <button className="track-play-btn" onClick={() => handlePlay(track)}>
                    {active && isPlaying ? '⏸' : '▶'}
                  </button>
                  {track.title}
                </td>
                <td className="track-duration">{fmt(track.duration_ms)}</td>
                <td className="track-bitrate">{track.bitrate_kbps ? `${track.bitrate_kbps} kbps` : ''}</td>
                <td className="track-play-count">{track.play_count > 0 ? `${track.play_count} plays` : ''}</td>
                <td className="track-actions"><AddToPlaylistMenu trackId={track.id} /></td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
