import { useEffect, useRef } from 'react'
import { Vibrant } from 'node-vibrant/browser'

const DEFAULT        = '#a855f7'
const DEFAULT_HOVER  = '#c084fc'
const DEFAULT2       = '#7e22ce'
const DURATION = 500

function hexToRgb(hex) {
  return [
    parseInt(hex.slice(1, 3), 16),
    parseInt(hex.slice(3, 5), 16),
    parseInt(hex.slice(5, 7), 16),
  ]
}

function rgbToHex(r, g, b) {
  const h = (n) => Math.round(Math.max(0, Math.min(255, n))).toString(16).padStart(2, '0')
  return `#${h(r)}${h(g)}${h(b)}`
}

function hslToHex(h, s, l) {
  h = ((h % 1) + 1) % 1
  s = Math.max(0, Math.min(1, s))
  l = Math.max(0, Math.min(1, l))
  const a = s * Math.min(l, 1 - l)
  const f = (n) => {
    const k = (n + h * 12) % 12
    const v = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1)
    return Math.round(Math.max(0, Math.min(1, v)) * 255).toString(16).padStart(2, '0')
  }
  return `#${f(0)}${f(8)}${f(4)}`
}

function rgbToHsl(r, g, b) {
  r /= 255; g /= 255; b /= 255
  const max = Math.max(r, g, b), min = Math.min(r, g, b)
  const l = (max + min) / 2
  const d = max - min
  if (d === 0) return [0, 0, l]
  const s = d / (1 - Math.abs(2 * l - 1))
  let h = 0
  if (max === r)      h = ((g - b) / d + 6) % 6
  else if (max === g) h = (b - r) / d + 2
  else                h = (r - g) / d + 4
  return [h / 6, s, l]
}

function adjustHex(hex, targetL) {
  const [r, g, b] = hexToRgb(hex)
  const [h, s] = rgbToHsl(r, g, b)
  return hslToHex(h, s, targetL)
}

function clampedHex(swatch, minL, maxL) {
  const l = swatch.hsl[2]
  return (l >= minL && l <= maxL) ? swatch.hex : adjustHex(swatch.hex, Math.min(maxL, Math.max(minL, l)))
}

function applyColors(accent, hover, accent2) {
  const root = document.documentElement
  root.style.setProperty('--accent', accent)
  root.style.setProperty('--accent-dim', accent + '33')
  root.style.setProperty('--accent-hover', hover)
  root.style.setProperty('--accent2', accent2)
}

function getCurrentHex(prop, fallback) {
  const v = document.documentElement.style.getPropertyValue(prop).trim()
  return (v && v.startsWith('#') && v.length === 7) ? v : fallback
}

export function useAlbumAccent(albumArtUrl) {
  const rafRef = useRef(null)

  useEffect(() => {
    const cancelAnim = () => {
      if (rafRef.current != null) { cancelAnimationFrame(rafRef.current); rafRef.current = null }
    }

    const animateTo = (toAccent, toHover, toAccent2) => {
      cancelAnim()
      const fromAccent  = getCurrentHex('--accent',  DEFAULT)
      const fromHover   = getCurrentHex('--accent-hover', DEFAULT_HOVER)
      const fromAccent2 = getCurrentHex('--accent2', DEFAULT2)
      if (fromAccent === toAccent && fromHover === toHover && fromAccent2 === toAccent2) return
      const [fAR, fAG, fAB]   = hexToRgb(fromAccent)
      const [tAR, tAG, tAB]   = hexToRgb(toAccent)
      const [fHR, fHG, fHB]   = hexToRgb(fromHover)
      const [tHR, tHG, tHB]   = hexToRgb(toHover)
      const [fA2R, fA2G, fA2B] = hexToRgb(fromAccent2)
      const [tA2R, tA2G, tA2B] = hexToRgb(toAccent2)
      const start = performance.now()
      const step = (now) => {
        const raw = Math.min(1, (now - start) / DURATION)
        const t = raw < 0.5 ? 2 * raw * raw : 1 - Math.pow(-2 * raw + 2, 2) / 2
        applyColors(
          rgbToHex(fAR  + (tAR  - fAR)  * t, fAG  + (tAG  - fAG)  * t, fAB  + (tAB  - fAB)  * t),
          rgbToHex(fHR  + (tHR  - fHR)  * t, fHG  + (tHG  - fHG)  * t, fHB  + (tHB  - fHB)  * t),
          rgbToHex(fA2R + (tA2R - fA2R) * t, fA2G + (tA2G - fA2G) * t, fA2B + (tA2B - fA2B) * t),
        )
        if (raw < 1) { rafRef.current = requestAnimationFrame(step) }
        else { rafRef.current = null }
      }
      rafRef.current = requestAnimationFrame(step)
    }

    if (!albumArtUrl) {
      animateTo(DEFAULT, DEFAULT_HOVER, DEFAULT2)
      return cancelAnim
    }

    let cancelled = false
    Vibrant.from(albumArtUrl).getPalette().then((palette) => {
      if (cancelled) return
      const vSwatch = palette.Vibrant ?? palette.LightVibrant ?? palette.DarkVibrant
      if (!vSwatch) { animateTo(DEFAULT, DEFAULT_HOVER, DEFAULT2); return }

      const [h, s, l] = vSwatch.hsl
      // Pin accent to a mid-range lightness so the +/-0.22 steps are always visible
      const baseL   = Math.min(0.72, Math.max(0.52, l))
      const accent  = hslToHex(h, s, baseL)
      const hover   = hslToHex(h, s, Math.min(0.92, baseL + 0.22))
      const accent2 = hslToHex(h, s, Math.max(0.40, baseL - 0.22))

      animateTo(accent, hover, accent2)
    }).catch(() => { if (!cancelled) animateTo(DEFAULT, DEFAULT_HOVER, DEFAULT2) })

    return () => { cancelled = true; cancelAnim() }
  }, [albumArtUrl])
}
