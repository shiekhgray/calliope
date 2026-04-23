import { useEffect, useRef } from 'react'
import { usePlayer } from '../player/PlayerContext'

// Module-level ref — pages write here; Layout's listener reads it
const firstTrackGetterRef = { current: null }

// Called from Layout once — global spacebar handler
export function useSpacebarPlayback() {
  const { isPlaying, togglePlay, playTrack } = usePlayer()

  useEffect(() => {
    const handler = (e) => {
      if (e.code !== 'Space') return
      const tag = e.target.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || e.target.isContentEditable) return
      e.preventDefault()

      if (isPlaying !== null) {
        togglePlay()
      } else {
        const track = firstTrackGetterRef.current?.()
        if (track) playTrack(track)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isPlaying, togglePlay, playTrack])
}

// Called from individual pages to register their first-track provider
export function useRegisterFirstTrack(getFirstTrack) {
  const fnRef = useRef(getFirstTrack)
  fnRef.current = getFirstTrack

  useEffect(() => {
    firstTrackGetterRef.current = () => fnRef.current()
    return () => { firstTrackGetterRef.current = null }
  }, [])
}
