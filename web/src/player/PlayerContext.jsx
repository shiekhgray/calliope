import { createContext, useContext, useState, useRef, useEffect } from 'react'
import api from '../api/client'

const PlayerContext = createContext(null)

// Single Audio element for the lifetime of the app
const audio = new Audio()

const STORAGE_KEY = 'calliope-player-state'

function saveState(track, queue, queueIndex) {
  if (!track) return
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      track, queue, queueIndex, progress: audio.currentTime,
    }))
  } catch {}
}

function loadSavedState() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

export function PlayerProvider({ children }) {
  const saved = useRef(loadSavedState())

  const [currentTrack, setCurrentTrack] = useState(saved.current?.track ?? null)
  const [queue, setQueue] = useState(saved.current?.queue ?? [])
  const [queueIndex, setQueueIndex] = useState(saved.current?.queueIndex ?? 0)
  const [isPlaying, setIsPlaying] = useState(saved.current?.track ? false : null)
  const [progress, setProgress] = useState(saved.current?.progress ?? 0)
  const [duration, setDuration] = useState(0)   // seconds
  const [volume, setVolumeState] = useState(1)  // 0–1

  // Radio mode — persisted to localStorage; default on
  const radioModeRef = useRef(localStorage.getItem('radioMode') !== 'false')
  const [radioMode, setRadioModeState] = useState(radioModeRef.current)

  // Track IDs played since last manual playTrack() call — used to avoid repeats in radio
  const sessionPlayedRef = useRef(new Set())

  // Play history — most-recent first, capped at 10
  const [history, setHistory] = useState([])

  // Refs that mirror queue/index/currentTrack state so event handlers (onended,
  // _extendWithRadio) can read current values without closures or nested setState
  // calls. Nested setState inside an updater double-fires under React StrictMode,
  // causing queueIndex to increment by 2 and every other track to be skipped.
  const queueRef = useRef(saved.current?.queue ?? [])
  const queueIndexRef = useRef(saved.current?.queueIndex ?? 0)
  const currentTrackRef = useRef(saved.current?.track ?? null)

  function _setQueue(q) { queueRef.current = q; setQueue(q) }
  function _setQueueIndex(i) { queueIndexRef.current = i; setQueueIndex(i) }
  function _setCurrentTrack(t) { currentTrackRef.current = t; setCurrentTrack(t) }

  // Restore audio src from saved state (seek after metadata loads; don't autoplay)
  useEffect(() => {
    const s = saved.current
    if (!s?.track) return
    audio.src = `/calliope/api/tracks/${s.track.id}/stream`
    audio.load()
    const onMeta = () => { audio.currentTime = s.progress ?? 0 }
    audio.addEventListener('loadedmetadata', onMeta, { once: true })
  }, [])

  // Save state when tab is hidden (before Chrome may discard it)
  useEffect(() => {
    const onHide = () => saveState(currentTrackRef.current, queueRef.current, queueIndexRef.current)
    window.addEventListener('pagehide', onHide)
    document.addEventListener('visibilitychange', onHide)
    return () => {
      window.removeEventListener('pagehide', onHide)
      document.removeEventListener('visibilitychange', onHide)
    }
  }, [])

  // Hold a Web Lock so Chrome deprioritises this tab for discard
  useEffect(() => {
    if (!navigator.locks) return
    let released = false
    navigator.locks.request('calliope-player', { mode: 'exclusive' }, () => new Promise(resolve => {
      // resolved only on unmount — keeps the lock for the app's lifetime
      const interval = setInterval(() => { if (released) { clearInterval(interval); resolve() } }, 1000)
    }))
    return () => { released = true }
  }, [])

  audio.ontimeupdate = () => setProgress(audio.currentTime)
  audio.ondurationchange = () => setDuration(audio.duration || 0)
  audio.onended = () => {
    setIsPlaying(false)
    const ct = currentTrackRef.current
    if (ct) {
      api.post(`/tracks/${ct.id}/played`).catch(() => {})
      setHistory((h) => [ct, ...h].slice(0, 10))
    }
    const q = queueRef.current
    const next = queueIndexRef.current + 1
    if (next < q.length) {
      _setQueueIndex(next)
      _loadTrack(q[next])
    } else if (radioModeRef.current) {
      _extendWithRadio()
    }
  }

  function _extendWithRadio() {
    const ct = currentTrackRef.current
    if (!ct) return
    sessionPlayedRef.current.add(ct.id)
    const seedAlbumId = ct.album_id
    api.get(`/tracks/${ct.id}/similar?limit=25`)
      .then((res) => {
        const candidates = res.data.filter(
          (t) => !sessionPlayedRef.current.has(t.id) && t.album_id !== seedAlbumId
        )
        if (candidates.length > 0) {
          const next = candidates[0]
          const newQueue = [...queueRef.current, next]
          _setQueue(newQueue)
          _setQueueIndex(newQueue.length - 1)
          _loadTrack(next)
        }
      })
      .catch(() => {})
  }

  function _loadTrack(track) {
    audio.src = `/calliope/api/tracks/${track.id}/stream`
    audio.load()
    audio.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false))
    _setCurrentTrack(track)
    setProgress(0)
  }

  function playTrack(track, trackList = []) {
    sessionStorage.removeItem(STORAGE_KEY)
    saved.current = null
    // Reset session tracking and history on every manual play
    sessionPlayedRef.current = new Set([track.id])
    setHistory([])
    const list = trackList.length ? trackList : [track]
    const idx = list.findIndex((t) => t.id === track.id)
    _setQueue(list)
    _setQueueIndex(idx >= 0 ? idx : 0)
    _loadTrack(track)
  }

  function togglePlay() {
    if (!currentTrackRef.current) return
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
    const q = queueRef.current
    const i = queueIndexRef.current
    const next = i + 1
    if (next < q.length) {
      const ct = currentTrackRef.current
      if (ct) setHistory((h) => [ct, ...h].slice(0, 10))
      _setQueueIndex(next)
      _loadTrack(q[next])
    } else if (radioModeRef.current) {
      const ct = currentTrackRef.current
      if (ct) setHistory((h) => [ct, ...h].slice(0, 10))
      _extendWithRadio()
    }
  }

  function skipPrev() {
    if (audio.currentTime > 3) {
      seek(0)
      return
    }
    const q = queueRef.current
    const prev = queueIndexRef.current - 1
    if (prev >= 0) {
      _setQueueIndex(prev)
      _loadTrack(q[prev])
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
