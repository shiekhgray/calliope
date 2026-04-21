import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { usePlayer } from '../player/PlayerContext'

function fmt(secs) {
  if (!secs || isNaN(secs)) return '0:00'
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

function VolumeControl({ volume, setVolume }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    function handle(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  const icon = volume === 0 ? '🔇' : volume < 0.5 ? '🔉' : '🔊'

  return (
    <div className="vol-wrap" ref={ref}>
      <button className="vol-btn" onClick={() => setOpen((v) => !v)} title="Volume">
        {icon}
      </button>
      {open && (
        <div className="vol-popup">
          <input
            type="range"
            min={0}
            max={1}
            step={0.02}
            value={volume}
            onChange={(e) => setVolume(Number(e.target.value))}
          />
        </div>
      )}
    </div>
  )
}

export default function PlayerBar() {
  const { currentTrack, isPlaying, progress, duration, volume, togglePlay, seek, skipNext, skipPrev, setVolume } = usePlayer()

  if (!currentTrack) return null

  return (
    <div className="player-bar">
      <div className="player-track-info">
        <span className="player-title">{currentTrack.title}</span>
        <div className="player-links">
          {currentTrack.album_id && currentTrack.album_title && (
            <Link to={`/albums/${currentTrack.album_id}`} className="player-link">
              {currentTrack.album_title}
            </Link>
          )}
          {currentTrack.album_id && currentTrack.album_title && currentTrack.artist_id && currentTrack.artist_name && (
            <span className="player-link-sep">·</span>
          )}
          {currentTrack.artist_id && currentTrack.artist_name && (
            <Link to={`/artists/${currentTrack.artist_id}`} className="player-link">
              {currentTrack.artist_name}
            </Link>
          )}
        </div>
      </div>

      <div className="player-controls">
        <button onClick={skipPrev} title="Previous">⏮</button>
        <button className="play-btn" onClick={togglePlay} title={isPlaying ? 'Pause' : 'Play'}>
          {isPlaying ? '⏸' : '▶'}
        </button>
        <button onClick={skipNext} title="Next">⏭</button>
      </div>

      <div className="player-progress">
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
        <VolumeControl volume={volume} setVolume={setVolume} />
      </div>
    </div>
  )
}
