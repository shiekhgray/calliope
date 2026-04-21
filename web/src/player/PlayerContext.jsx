import { createContext, useContext, useState, useRef } from 'react'
import api from '../api/client'

const PlayerContext = createContext(null)

// Single Audio element for the lifetime of the app
const audio = new Audio()

export function PlayerProvider({ children }) {
  const [currentTrack, setCurrentTrack] = useState(null)
  const [queue, setQueue] = useState([])
  const [queueIndex, setQueueIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [progress, setProgress] = useState(0)   // seconds
  const [duration, setDuration] = useState(0)   // seconds
  const [volume, setVolumeState] = useState(1)  // 0–1

  // Radio mode — persisted to localStorage; default on
  const radioModeRef = useRef(localStorage.getItem('radioMode') !== 'false')
  const [radioMode, setRadioModeState] = useState(radioModeRef.current)

  // Track IDs played since last manual playTrack() call — used to avoid repeats in radio
  const sessionPlayedRef = useRef(new Set())

  // Play history — most-recent first, capped at 10
  const [history, setHistory] = useState([])

  audio.ontimeupdate = () => setProgress(audio.currentTime)
  audio.ondurationchange = () => setDuration(audio.duration || 0)
  audio.onended = () => {
    setIsPlaying(false)
    setCurrentTrack((ct) => {
      if (ct) {
        api.post(`/tracks/${ct.id}/played`).catch(() => {})
        setHistory((h) => [ct, ...h].slice(0, 10))
      }
      return ct
    })
    setQueue((q) => {
      setQueueIndex((i) => {
        const next = i + 1
        if (next < q.length) {
          _loadTrack(q[next])
          return next
        }
        // Queue exhausted — extend via radio if enabled
        if (radioModeRef.current) {
          _extendWithRadio()
        }
        return i
      })
      return q
    })
  }

  function _extendWithRadio() {
    setCurrentTrack((ct) => {
      if (!ct) return ct
      sessionPlayedRef.current.add(ct.id)
      const seedAlbumId = ct.album_id
      api.get(`/tracks/${ct.id}/similar?limit=25`)
        .then((res) => {
          const candidates = res.data.filter(
            (t) => !sessionPlayedRef.current.has(t.id) && t.album_id !== seedAlbumId
          )
          if (candidates.length > 0) {
            const next = candidates[0]
            setQueue((q) => {
              const newQueue = [...q, next]
              setQueueIndex(newQueue.length - 1)
              _loadTrack(next)
              return newQueue
            })
          }
        })
        .catch(() => {})
      return ct
    })
  }

  function _loadTrack(track) {
    audio.src = `/calliope/api/tracks/${track.id}/stream`
    audio.load()
    audio.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false))
    setCurrentTrack(track)
    setProgress(0)
  }

  function playTrack(track, trackList = []) {
    // Reset session tracking and history on every manual play
    sessionPlayedRef.current = new Set([track.id])
    setHistory([])
    const list = trackList.length ? trackList : [track]
    const idx = list.findIndex((t) => t.id === track.id)
    setQueue(list)
    setQueueIndex(idx >= 0 ? idx : 0)
    _loadTrack(track)
  }

  function togglePlay() {
    if (!currentTrack) return
    if (audio.paused) {
      audio.play().then(() => setIsPlaying(true))
    } else {
      audio.pause()
      setIsPlaying(false)
    }
  }

  function seek(seconds) {
    audio.currentTime = seconds
    setProgress(seconds)
  }

  function setVolume(v) {
    audio.volume = v
    setVolumeState(v)
  }

  function skipNext() {
    const next = queueIndex + 1
    if (next < queue.length) {
      if (currentTrack) setHistory((h) => [currentTrack, ...h].slice(0, 10))
      setQueueIndex(next)
      _loadTrack(queue[next])
    }
  }

  function skipPrev() {
    if (progress > 3) {
      seek(0)
      return
    }
    const prev = queueIndex - 1
    if (prev >= 0) {
      setQueueIndex(prev)
      _loadTrack(queue[prev])
    }
  }

  function toggleRadioMode() {
    const next = !radioModeRef.current
    radioModeRef.current = next
    setRadioModeState(next)
    localStorage.setItem('radioMode', String(next))
  }

  return (
    <PlayerContext.Provider value={{
      currentTrack, isPlaying, progress, duration, volume, radioMode,
      history, queue, queueIndex,
      playTrack, togglePlay, seek, skipNext, skipPrev, setVolume, toggleRadioMode,
    }}>
      {children}
    </PlayerContext.Provider>
  )
}

export function usePlayer() {
  return useContext(PlayerContext)
}
