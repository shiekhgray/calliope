import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { usePlayer } from '../player/PlayerContext'
import api from '../api/client'

function fmt(secs) {
  if (!secs || isNaN(secs)) return '0:00'
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

function Equalizer() {
  return (
    <span className="np-equalizer" aria-hidden="true">
      <span /><span /><span />
    </span>
  )
}

export default function NowPlayingPage() {
  const {
    currentTrack, isPlaying, progress, duration, volume, radioMode,
    history, queue, queueIndex,
    playTrack, togglePlay, seek, skipNext, skipPrev, setVolume, toggleRadioMode,
  } = usePlayer()

  const upNext = queue.slice(queueIndex + 1, queueIndex + 3)
  const played = history.slice(0, 2).reverse()

  const { data: albumData } = useQuery({
    queryKey: ['album', currentTrack?.album_id],
    queryFn: () => api.get(`/albums/${currentTrack.album_id}`).then((r) => r.data),
    enabled: !!currentTrack?.album_id,
  })

  const { data: similar } = useQuery({
    queryKey: ['similar', currentTrack?.id],
    queryFn: () => api.get(`/tracks/${currentTrack.id}/similar?limit=5`).then((r) => r.data),
    enabled: !!currentTrack?.id,
  })

  if (!currentTrack) {
    return (
      <div className="page np-empty">
        <p className="np-empty-msg">Nothing playing</p>
        <Link to="/">Go to library</Link>
      </div>
    )
  }

  const radioSlots = radioMode ? Math.max(0, 2 - upNext.length) : 0

  return (
    <div className="now-playing-page">
      {/* ── Left column ── */}
      <div className="np-left">
        {currentTrack.album_id ? (
          <img
            className="np-art"
            src={`/calliope/api/albums/${currentTrack.album_id}/art`}
            alt={currentTrack.album_title ?? ''}
          />
        ) : (
          <div className="np-art np-art-placeholder">♪</div>
        )}

        <div className="np-track-title">{currentTrack.title}</div>
        <div className="np-track-meta">
          {currentTrack.artist_id && currentTrack.artist_name && (
            <Link to={`/artists/${currentTrack.artist_id}`}>{currentTrack.artist_name}</Link>
          )}
          {currentTrack.album_id && currentTrack.album_title && (
            <> · <Link to={`/albums/${currentTrack.album_id}`}>{currentTrack.album_title}</Link></>
          )}
          {albumData?.year && <> · {albumData.year}</>}
        </div>

        <div className="np-scrubber">
          <span>{fmt(progress)}</span>
          <input
            type="range"
            min={0}
            max={duration || 0}
            step={1}
            value={progress}
            onChange={(e) => seek(Number(e.target.value))}
          />
          <span>{fmt(duration)}</span>
        </div>

        <div className="np-controls">
          <button onClick={skipPrev} title="Previous">⏮</button>
          <button onClick={() => seek(Math.max(0, progress - 15))} title="Back 15s">⏪</button>
          <button className="play-btn" onClick={togglePlay} title={isPlaying ? 'Pause' : 'Play'}>
            {isPlaying ? '⏸' : '▶'}
          </button>
          <button onClick={() => seek(Math.min(duration, progress + 15))} title="Forward 15s">⏩</button>
          <button onClick={skipNext} title="Next">⏭</button>
        </div>

        <div className="np-bottom-controls">
          <input
            type="range"
            className="np-volume"
            min={0}
            max={1}
            step={0.02}
            value={volume}
            onChange={(e) => setVolume(Number(e.target.value))}
          />
          <button
            className={`radio-btn${radioMode ? ' radio-btn--on' : ''}`}
            onClick={toggleRadioMode}
            title={radioMode ? 'Radio: on' : 'Radio: off'}
          >
            ≋
          </button>
        </div>
      </div>

      {/* ── Right column ── */}
      <div className="np-right">
        {played.length > 0 && (
          <div className="np-queue-section">
            <div className="np-section-label">Played</div>
            {played.map((t, i) => (
              <Link
                key={`played-${t.id}-${i}`}
                to={`/albums/${t.album_id}`}
                className="np-queue-track np-queue-track--muted"
              >
                <span className="np-qt-title">{t.title}</span>
                <span className="np-qt-sep"> — </span>
                <span className="np-qt-artist">{t.artist_name}</span>
              </Link>
            ))}
          </div>
        )}

        <div className="np-queue-section">
          <div className="np-section-label">Now Playing</div>
          <div className="np-queue-track np-queue-track--current">
            <Equalizer />
            <span className="np-qt-title">{currentTrack.title}</span>
            <span className="np-qt-sep"> — </span>
            <span className="np-qt-artist">{currentTrack.artist_name}</span>
          </div>
        </div>

        {(upNext.length > 0 || radioSlots > 0) && (
          <div className="np-queue-section">
            <div className="np-section-label">Up Next</div>
            {upNext.map((t, i) => (
              <div key={`next-${t.id}-${i}`} className="np-queue-track">
                <span className="np-qt-title">{t.title}</span>
                <span className="np-qt-sep"> — </span>
                <span className="np-qt-artist">{t.artist_name}</span>
              </div>
            ))}
            {Array.from({ length: radioSlots }).map((_, i) => (
              <div key={`radio-slot-${i}`} className="np-queue-track np-queue-track--muted">
                Radio will continue…
              </div>
            ))}
          </div>
        )}

        {similar && similar.length > 0 && (
          <div className="np-queue-section">
            <div className="np-section-label">Similar</div>
            {similar.map((t) => (
              <button
                key={t.id}
                className="np-similar-track"
                onClick={() => playTrack(t)}
              >
                <span className="np-qt-title">{t.title}</span>
                <span className="np-qt-sep"> · </span>
                <span className="np-qt-artist">{t.artist_name}</span>
                <span className="np-qt-sep"> · </span>
                <span className="np-qt-album">{t.album_title}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
