import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import api from '../api/client'
import { usePlayer } from '../player/PlayerContext'
import { useAuth } from '../auth/AuthContext'
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

// Inline artist search + dropdown used for both track credits and album artists
function ArtistSearchInput({ onSelect, onClose }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const inputRef = useRef(null)
  const wrapRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    if (!q.trim()) { setResults([]); return }
    setLoading(true)
    const timeout = setTimeout(() => {
      api.get('/search', { params: { q: q.trim() } })
        .then((r) => setResults(r.data.artists ?? []))
        .catch(() => setResults([]))
        .finally(() => setLoading(false))
    }, 200)
    return () => clearTimeout(timeout)
  }, [q])

  // Close on outside click
  useEffect(() => {
    function handle(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) onClose()
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [onClose])

  return (
    <div className="credit-search-wrap" ref={wrapRef}>
      <input
        ref={inputRef}
        className="credit-search-input"
        placeholder="Search artist…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Escape') onClose() }}
      />
      {(results.length > 0 || loading) && (
        <div className="credit-search-dropdown">
          {loading && <div className="credit-search-loading">…</div>}
          {results.map((artist) => (
            <button
              key={artist.id}
              className="credit-search-item"
              onMouseDown={(e) => { e.preventDefault(); onSelect(artist) }}
            >
              {artist.name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// Credit chip — shows artist name; owner can click to remove
function CreditChip({ credit, onRemove, isOwner }) {
  const [confirming, setConfirming] = useState(false)

  if (!isOwner) {
    return (
      <span className="credit-chip">
        feat. <Link to={`/artists/${credit.artist_id}`}>{credit.artist_name}</Link>
      </span>
    )
  }

  if (confirming) {
    return (
      <span className="credit-chip credit-chip--confirming">
        feat. {credit.artist_name}
        <button
          className="credit-chip-remove"
          title="Confirm remove"
          onClick={() => { setConfirming(false); onRemove(credit.artist_id) }}
        >
          ×
        </button>
        <button
          className="credit-chip-cancel"
          title="Cancel"
          onClick={() => setConfirming(false)}
        >
          ↩
        </button>
      </span>
    )
  }

  return (
    <span
      className="credit-chip credit-chip--owner"
      onClick={() => setConfirming(true)}
      title="Click to remove credit"
    >
      feat. <Link
        to={`/artists/${credit.artist_id}`}
        onClick={(e) => e.stopPropagation()}
      >
        {credit.artist_name}
      </Link>
    </span>
  )
}

// Per-track credit row with add/remove
function TrackCredits({ track, albumId, isOwner }) {
  const queryClient = useQueryClient()
  const [adding, setAdding] = useState(false)

  const addMutation = useMutation({
    mutationFn: (artistId) => api.post(`/tracks/${track.id}/credits`, { artist_id: artistId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['album', String(albumId)] })
      setAdding(false)
    },
  })

  const removeMutation = useMutation({
    mutationFn: (artistId) => api.delete(`/tracks/${track.id}/credits/${artistId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['album', String(albumId)] })
    },
  })

  const credits = track.credits ?? []

  if (!isOwner && credits.length === 0) return null

  return (
    <div className="track-credits-row">
      {credits.map((c) => (
        <CreditChip
          key={c.artist_id}
          credit={c}
          isOwner={isOwner}
          onRemove={(artistId) => removeMutation.mutate(artistId)}
        />
      ))}
      {isOwner && (
        adding ? (
          <ArtistSearchInput
            onSelect={(artist) => addMutation.mutate(artist.id)}
            onClose={() => setAdding(false)}
          />
        ) : (
          <button
            className="credit-add-btn"
            title="Add track credit"
            onClick={() => setAdding(true)}
          >
            +
          </button>
        )
      )}
    </div>
  )
}

// Album-level credits management (owner only collapsible section)
function AlbumCreditsSection({ albumId, isOwner }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [adding, setAdding] = useState(false)

  const { data: albumArtists = [], isLoading } = useQuery({
    queryKey: ['album-artists', albumId],
    queryFn: () => api.get(`/albums/${albumId}/artists`).then((r) => r.data),
    enabled: open,
  })

  const addMutation = useMutation({
    mutationFn: (artistId) => api.post(`/albums/${albumId}/artists`, { artist_id: artistId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['album-artists', albumId] })
      setAdding(false)
    },
  })

  const removeMutation = useMutation({
    mutationFn: (artistId) => api.delete(`/albums/${albumId}/artists/${artistId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['album-artists', albumId] })
    },
  })

  if (!isOwner) return null

  return (
    <div className="album-credits-section">
      <button
        className="album-credits-toggle"
        onClick={() => setOpen((v) => !v)}
      >
        Album Credits {open ? '▴' : '▾'}
      </button>
      {open && (
        <div className="album-credits-body">
          {isLoading && <span className="credit-loading">Loading…</span>}
          <div className="album-credits-chips">
            {albumArtists.map((aa) => {
              const credit = { artist_id: aa.artist_id, artist_name: aa.artist_name }
              return (
                <CreditChip
                  key={aa.artist_id}
                  credit={credit}
                  isOwner={isOwner}
                  onRemove={(artistId) => removeMutation.mutate(artistId)}
                />
              )
            })}
            {adding ? (
              <ArtistSearchInput
                onSelect={(artist) => addMutation.mutate(artist.id)}
                onClose={() => setAdding(false)}
              />
            ) : (
              <button
                className="credit-add-btn"
                title="Add album artist credit"
                onClick={() => setAdding(true)}
              >
                +
              </button>
            )}
          </div>
        </div>
      )}
    </div>
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
  const { userId } = useAuth()
  const queryClient = useQueryClient()
  const fileInputRef = useRef(null)
  const highlightRef = useRef(null)
  const [artVersion, setArtVersion] = useState(0)
  const [artUploading, setArtUploading] = useState(false)
  const [autoPlayAttempted, setAutoPlayAttempted] = useState(false)

  const isOwner = userId === 1

  const TYPE_CYCLE = { album: 'ep', ep: 'single', single: 'album' }
  const TYPE_LABEL = { album: 'Album', ep: 'EP', single: 'Single' }

  const typeMutation = useMutation({
    mutationFn: (newType) => api.patch(`/albums/${id}/type`, { album_type: newType }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['album', id] })
      queryClient.invalidateQueries({ queryKey: ['artist-albums', String(data.data.artist_id)] })
      queryClient.invalidateQueries({ queryKey: ['artist-singles', String(data.data.artist_id)] })
    },
  })

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

  const { data: albumArtists = [] } = useQuery({
    queryKey: ['album-artists', id],
    queryFn: () => api.get(`/albums/${id}/artists`).then((r) => r.data),
    enabled: !!album,
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
          <p className="album-artist">
            {albumArtists.length > 0
              ? albumArtists.map((aa, i) => (
                  <span key={aa.artist_id}>
                    {i > 0 && ' · '}
                    <Link to={`/artists/${aa.artist_id}`}>{aa.artist_name}</Link>
                  </span>
                ))
              : <Link to={`/artists/${album.artist_id}`}>{album.artist_name}</Link>
            }
          </p>
          {album.year && <p className="album-year">{album.year}</p>}
          {isOwner ? (
            <button
              className="album-type-pill album-type-pill--owner"
              onClick={() => typeMutation.mutate(TYPE_CYCLE[album.album_type] ?? 'album')}
              disabled={typeMutation.isPending}
              title="Click to change type"
            >
              {TYPE_LABEL[album.album_type] ?? 'Album'}
            </button>
          ) : (
            album.album_type !== 'album' && (
              <span className="album-type-pill">
                {TYPE_LABEL[album.album_type]}
              </span>
            )
          )}
          <button
            className="play-all-btn"
            onClick={() => tracks.length && handlePlay(tracks[0])}
          >
            ▶ Play all
          </button>
          <AlbumCreditsSection albumId={id} isOwner={isOwner} />
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
                <td className="track-name">
                  <button className="track-play-btn" onClick={() => handlePlay(track)}>
                    {active && isPlaying ? '⏸' : '▶'}
                  </button>
                  <span className="track-name-inner">
                    {track.title}
                    <TrackCredits track={track} albumId={id} isOwner={isOwner} />
                  </span>
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
