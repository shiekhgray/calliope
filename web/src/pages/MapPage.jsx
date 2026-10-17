import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import { usePlayer } from '../player/PlayerContext'

// 16 evenly-spaced, well-separated categorical hues for clusters.
const CLUSTER_PALETTE = Array.from({ length: 16 }, (_, i) => {
  const hue = (i * 360 / 16 + (i % 2) * 18) % 360
  return hslToRgb(hue, 0.62, 0.58)
})

function hslToRgb(h, s, l) {
  h /= 360
  const a = s * Math.min(l, 1 - l)
  const f = (n) => {
    const k = (n + h * 12) % 12
    return Math.round(255 * (l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1))))
  }
  return [f(0), f(8), f(4)]
}

export default function MapPage() {
  const { currentTrack, playTrack } = usePlayer()
  const canvasRef = useRef(null)
  const wrapRef = useRef(null)

  // View transform + interaction state held in refs (avoid re-render churn).
  const view = useRef({ scale: 1, tx: 0, ty: 0, fitted: false })
  const drag = useRef(null)
  const [hover, setHover] = useState(null) // { point, sx, sy }

  const [lens, setLens] = useState('cluster')

  // ---- data ----
  const { data: points = [], isLoading } = useQuery({
    queryKey: ['map'],
    queryFn: () => api.get('/map').then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  })

  // 3-PC gestalt values.
  const { data: pcaVals } = useQuery({
    queryKey: ['map-pca'],
    queryFn: () => api.get('/map/pca').then((r) => r.data),
    enabled: lens === 'pca',
    staleTime: 5 * 60 * 1000,
  })

  // Now-playing radio neighborhood.
  const { data: similar = [] } = useQuery({
    queryKey: ['map-similar', currentTrack?.id],
    queryFn: () => api.get(`/tracks/${currentTrack.id}/similar`, { params: { limit: 25 } }).then((r) => r.data),
    enabled: !!currentTrack?.id,
    staleTime: 60 * 1000,
  })
  const similarIds = useMemo(() => new Set(similar.map((t) => t.id)), [similar])

  // ---- color resolution ----
  const colorFor = useMemo(() => {
    return (p) => {
      if (lens === 'pca') {
        const c = pcaVals?.[p.track_id]
        return c ? [c[0] * 255, c[1] * 255, c[2] * 255] : [90, 90, 100]
      }
      const cid = p.cluster_id
      return CLUSTER_PALETTE[((cid ?? 0) % CLUSTER_PALETTE.length + CLUSTER_PALETTE.length) % CLUSTER_PALETTE.length]
    }
  }, [lens, pcaVals])

  // ---- bounds + fit ----
  const bounds = useMemo(() => {
    if (!points.length) return null
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
    for (const p of points) {
      if (p.x < minX) minX = p.x
      if (p.x > maxX) maxX = p.x
      if (p.y < minY) minY = p.y
      if (p.y > maxY) maxY = p.y
    }
    return { minX, maxX, minY, maxY }
  }, [points])

  function worldToScreen(p) {
    const v = view.current
    return [(p.x * v.scale) + v.tx, (p.y * v.scale) + v.ty]
  }

  function fit() {
    const canvas = canvasRef.current
    if (!canvas || !bounds) return
    const w = canvas.clientWidth, h = canvas.clientHeight
    const pad = 40
    const sx = (w - pad * 2) / ((bounds.maxX - bounds.minX) || 1)
    const sy = (h - pad * 2) / ((bounds.maxY - bounds.minY) || 1)
    const scale = Math.min(sx, sy)
    view.current = {
      scale,
      tx: pad - bounds.minX * scale + (w - pad * 2 - (bounds.maxX - bounds.minX) * scale) / 2,
      ty: pad - bounds.minY * scale + (h - pad * 2 - (bounds.maxY - bounds.minY) * scale) / 2,
      fitted: true,
    }
    draw()
  }

  // ---- drawing ----
  function draw() {
    const canvas = canvasRef.current
    if (!canvas || !points.length) return
    const dpr = window.devicePixelRatio || 1
    const w = canvas.clientWidth, h = canvas.clientHeight
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr
      canvas.height = h * dpr
    }
    const ctx = canvas.getContext('2d')
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, w, h)
    ctx.fillStyle = '#0c0c12'
    ctx.fillRect(0, 0, w, h)

    const baseR = Math.max(1.6, Math.min(4, view.current.scale * 0.06))
    const curId = currentTrack?.id

    // Dim non-highlighted points when something is playing.
    const dimming = !!curId

    for (const p of points) {
      const [x, y] = worldToScreen(p)
      if (x < -10 || x > w + 10 || y < -10 || y > h + 10) continue
      const [r, g, b] = colorFor(p)
      const isCur = p.track_id === curId
      const isNbr = similarIds.has(p.track_id)
      let alpha = dimming && !isCur && !isNbr ? 0.28 : 0.9
      ctx.beginPath()
      ctx.arc(x, y, isCur ? baseR * 2.4 : isNbr ? baseR * 1.5 : baseR, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(${r|0},${g|0},${b|0},${alpha})`
      ctx.fill()
      if (isCur) {
        ctx.lineWidth = 2
        ctx.strokeStyle = '#fff'
        ctx.stroke()
      } else if (isNbr) {
        ctx.lineWidth = 1
        ctx.strokeStyle = 'rgba(255,255,255,0.6)'
        ctx.stroke()
      }
    }

    // Hover ring
    if (hover) {
      const [x, y] = worldToScreen(hover.point)
      ctx.beginPath()
      ctx.arc(x, y, baseR + 4, 0, Math.PI * 2)
      ctx.lineWidth = 1.5
      ctx.strokeStyle = '#fff'
      ctx.stroke()
    }
  }

  // Initial fit once points + canvas are ready.
  useEffect(() => {
    if (points.length && !view.current.fitted) fit()
    else draw()
  })

  // Redraw when color inputs change.
  useEffect(() => { draw() }, [colorFor, similarIds, hover, currentTrack]) // eslint-disable-line react-hooks/exhaustive-deps

  // ---- interaction ----
  function findNearest(sx, sy) {
    let best = null, bestD = 100
    for (const p of points) {
      const [x, y] = worldToScreen(p)
      const d = (x - sx) ** 2 + (y - sy) ** 2
      if (d < bestD) { bestD = d; best = p }
    }
    return best
  }

  function onMouseDown(e) {
    const rect = canvasRef.current.getBoundingClientRect()
    drag.current = { x: e.clientX, y: e.clientY, moved: false, tx: view.current.tx, ty: view.current.ty, rect }
  }
  function onMouseMove(e) {
    const rect = canvasRef.current.getBoundingClientRect()
    const sx = e.clientX - rect.left, sy = e.clientY - rect.top
    if (drag.current) {
      const dx = e.clientX - drag.current.x, dy = e.clientY - drag.current.y
      if (Math.abs(dx) + Math.abs(dy) > 3) drag.current.moved = true
      view.current.tx = drag.current.tx + dx
      view.current.ty = drag.current.ty + dy
      if (hover) setHover(null)
      draw()
      return
    }
    const p = findNearest(sx, sy)
    if (p) setHover({ point: p, sx, sy })
    else if (hover) setHover(null)
  }
  function onMouseUp(e) {
    const d = drag.current
    drag.current = null
    if (d && !d.moved) {
      const rect = canvasRef.current.getBoundingClientRect()
      const p = findNearest(e.clientX - rect.left, e.clientY - rect.top)
      if (p) {
        playTrack({
          id: p.track_id, title: p.track_title,
          album_id: p.album_id, album_title: p.album_title,
          artist_id: p.artist_id, artist_name: p.artist_name,
        })
      }
    }
  }
  function onMouseLeave() { drag.current = null; setHover(null) }

  // Native wheel listener (needs passive:false to preventDefault).
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    function onWheel(e) {
      e.preventDefault()
      const rect = canvas.getBoundingClientRect()
      const mx = e.clientX - rect.left, my = e.clientY - rect.top
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12
      const v = view.current
      const wx = (mx - v.tx) / v.scale, wy = (my - v.ty) / v.scale
      v.scale *= factor
      v.tx = mx - wx * v.scale
      v.ty = my - wy * v.scale
      setHover(null)
      draw()
    }
    canvas.addEventListener('wheel', onWheel, { passive: false })
    return () => canvas.removeEventListener('wheel', onWheel)
  })

  // Redraw on container resize.
  useEffect(() => {
    const ro = new ResizeObserver(() => draw())
    if (wrapRef.current) ro.observe(wrapRef.current)
    return () => ro.disconnect()
  })

  return (
    <div className="map-page">
      <div className="map-toolbar">
        <h2>Music Map</h2>
        <div className="map-controls">
          <label>
            Color
            <select value={lens} onChange={(e) => setLens(e.target.value)}>
              <option value="cluster">Clusters</option>
              <option value="pca">3-PC gestalt</option>
            </select>
          </label>
          <button onClick={() => fit()}>Reset view</button>
        </div>
      </div>

      <div className="map-body">
        <div className="map-canvas-wrap" ref={wrapRef}>
          {isLoading && <div className="map-empty">Loading atlas…</div>}
          {!isLoading && !points.length && (
            <div className="map-empty">No atlas yet — rescan the library to build the map.</div>
          )}
          <canvas
            ref={canvasRef}
            className="map-canvas"
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onMouseLeave={onMouseLeave}
          />
          {hover && (
            <div
              className="map-tooltip"
              style={{ left: hover.sx + 14, top: hover.sy + 14 }}
            >
              <img
                src={`/calliope/api/albums/${hover.point.album_id}/art`}
                alt=""
                loading="lazy"
                onError={(e) => { e.target.style.visibility = 'hidden' }}
              />
              <div className="map-tooltip-text">
                <div className="map-tt-track">{hover.point.track_title}</div>
                <div className="map-tt-artist">{hover.point.artist_name}</div>
                <div className="map-tt-album">{hover.point.album_title}</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
