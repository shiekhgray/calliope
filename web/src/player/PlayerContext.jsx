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

  audio.ontimeupdate = () => setProgress(audio.currentTime)
  audio.ondurationchange = () => setDuration(audio.duration || 0)
  audio.onended = () => {
    setIsPlaying(false)
    // record the play before advancing
    setCurrentTrack((ct) => {
      if (ct) api.post(`/tracks/${ct.id}/played`).catch(() => {})
      return ct
    })
    // auto-advance
    setQueue((q) => {
      setQueueIndex((i) => {
        const next = i + 1
        if (next < q.length) {
          _loadTrack(q[next])
          return next
        }
        return i
      })
      return q
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

  return (
    <PlayerContext.Provider value={{
      currentTrack, isPlaying, progress, duration, volume,
      playTrack, togglePlay, seek, skipNext, skipPrev, setVolume,
    }}>
      {children}
    </PlayerContext.Provider>
  )
}

export function usePlayer() {
  return useContext(PlayerContext)
}
