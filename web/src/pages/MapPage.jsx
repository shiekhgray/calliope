import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { usePlayer } from '../player/PlayerContext'

// 9 similarity-weight groups, in DIM_SLICES order (must match the API).
const WEIGHT_KEYS = [
  'timbre', 'timbral_variation', 'harmony', 'chord_movement', 'tempo',
  'loudness', 'dynamic_range', 'brightness', 'tonal',
]

const WEIGHT_GROUPS = [
  { label: 'Timbre', rows: [
    { key: 'timbre', label: 'Tone Color' },
    { key: 'timbral_variation', label: 'Timbral Variation' },
    { key: 'brightness', label: 'Brightness' },
  ] },
  { label: 'Harmony', rows: [
    { key: 'harmony', label: 'Harmonic Content' },
    { key: 'chord_movement', label: 'Chord Movement' },
    { key: 'tonal', label: 'Tonal Character' },
  ] },
  { label: 'Rhythm & Energy', rows: [
    { key: 'tempo', label: 'Tempo' },
    { key: 'loudness', label: 'Loudness' },
    { key: 'dynamic_range', label: 'Dynamic Range' },
  ] },
]

const FEATURES = [
  { key: 'timbre', label: 'Tone Color' },
  { key: 'timbral_variation', label: 'Timbral Variation' },
  { key: 'harmony', label: 'Harmonic Content' },
  { key: 'chord_movement', label: 'Chord Movement' },
  { key: 'tempo', label: 'Tempo' },
  { key: 'loudness', label: 'Loudness' },
  { key: 'dynamic_range', label: 'Dynamic Range' },
  { key: 'brightness', label: 'Brightness' },
  { key: 'tonal', label: 'Tonal Character' },
]

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

// Viridis-ish perceptual ramp for the single-feature gradient lens.
const VIRIDIS = [
  [68, 1, 84], [59, 82, 139], [33, 145, 140], [94, 201, 98], [253, 231, 37],
]
function viridis(t) {
  t = Math.max(0, Math.min(1, t))
  const seg = t * (VIRIDIS.length - 1)
  const i = Math.min(VIRIDIS.length - 2, Math.floor(seg))
  const f = seg - i
  const a = VIRIDIS[i], b = VIRIDIS[i + 1]
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f]
}

export default function MapPage() {
  const qc = useQueryClient()
  const { currentTrack, playTrack } = usePlayer()
  const canvasRef = useRef(null)
  const wrapRef = useRef(null)

  // View transform + interaction state held in refs (avoid re-render churn).
  const view = useRef({ scale: 1, tx: 0, ty: 0, fitted: false })
  const drag = useRef(null)
  const [hover, setHover] = useState(null) // { point, sx, sy }

  const [lens, setLens] = useState('cluster')
  const [feature, setFeature] = useState('tempo')
  const [showPanel, setShowPanel] = useState(false)
  const [weights, setWeights] = useState(null)
  const [weightClusters, setWeightClusters] = useState(null) // {track_id: cid} live recolor

  // ---- data ----
  const { data: points = [], isLoading } = useQuery({
    queryKey: ['map'],
    queryFn: () => api.get('/map').then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  })

  const { data: me } = useQuery({
    queryKey: ['me'],
    queryFn: () => api.get('/auth/me').then((r) => r.data),
    staleTime: Infinity,
  })

  useEffect(() => {
    if (me && !weights) {
      setWeights(Object.fromEntries(WEIGHT_KEYS.map((k) => [k, me[`sim_weight_${k}`]])))
    }
  }, [me]) // eslint-disable-line react-hooks/exhaustive-deps

  // Single-feature lens values.
  const { data: lensVals } = useQuery({
    queryKey: ['map-lens', feature],
    queryFn: () => api.get('/map/lens', { params: { feature } }).then((r) => r.data),
    enabled: lens === 'feature',
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

  // ---- live recolor on slider drag (debounced) ----
  useEffect(() => {
    if (lens !== 'cluster' || !weights || !showPanel) return
    const w = WEIGHT_KEYS.map((k) => weights[k]).join(',')
    const t = setTimeout(() => {
      api.get('/map/clusters', { params: { weighted: true, w } })
        .then((r) => setWeightClusters(r.data))
    }, 250)
    return () => clearTimeout(t)
  }, [weights, lens, showPanel])

  const saveMutation = useMutation({
    mutationFn: (w) => api.put('/auth/similarity-weights', w),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['me'] })
      if (currentTrack) qc.invalidateQueries({ queryKey: ['similar', currentTrack.id] })
      qc.invalidateQueries({ queryKey: ['map-similar', currentTrack?.id] })
    },
  })

  // ---- color resolution ----
  const colorFor = useMemo(() => {
    return (p) => {
      if (lens === 'feature') {
        const v = lensVals?.[p.track_id]
        return v == null ? [90, 90, 100] : viridis(v)
      }
      if (lens === 'pca') {
        const c = pcaVals?.[p.track_id]
        return c ? [c[0] * 255, c[1] * 255, c[2] * 255] : [90, 90, 100]
      }
      const cid = weightClusters ? weightClusters[p.track_id] : p.cluster_id
      return CLUSTER_PALETTE[((cid ?? 0) % CLUSTER_PALETTE.length + CLUSTER_PALETTE.length) % CLUSTER_PALETTE.length]
    }
  }, [lens, lensVals, pcaVals, weightClusters])

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

  function setWeight(key, value) {
    setWeights((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <div className="map-page">
      <div className="map-toolbar">
        <h2>Music Map</h2>
        <div className="map-controls">
          <label>
            Color
            <select value={lens} onChange={(e) => { setLens(e.target.value); setWeightClusters(null) }}>
              <option value="cluster">Clusters</option>
              <option value="feature">Single feature</option>
              <option value="pca">3-PC gestalt</option>
            </select>
          </label>
          {lens === 'feature' && (
            <label>
              Feature
              <select value={feature} onChange={(e) => setFeature(e.target.value)}>
                {FEATURES.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
              </select>
            </label>
          )}
          <button onClick={() => fit()}>Reset view</button>
          {lens === 'cluster' && (
            <button onClick={() => setShowPanel((v) => !v)}>
              {showPanel ? 'Hide tuning' : 'Tune weights'}
            </button>
          )}
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

        {showPanel && lens === 'cluster' && weights && (
          <aside className="map-tune-panel">
            <h3>Sound Matching</h3>
            <p className="map-tune-hint">Drag to recolor clusters live. Save to make it your default.</p>
            {WEIGHT_GROUPS.map((group) => (
              <div key={group.label} className="sim-weights-group">
                <div className="sim-weights-group-label">{group.label}</div>
                {group.rows.map(({ key, label }) => (
                  <div key={key} className="sim-weight-row">
                    <div className="sim-weight-label">{label}</div>
                    <input
                      type="range" min={0} max={10} step={1}
                      value={weights[key]}
                      onChange={(e) => setWeight(key, Number(e.target.value))}
                      className="sim-weight-slider"
                    />
                    <div className="sim-weight-value">{weights[key]}</div>
                  </div>
                ))}
              </div>
            ))}
            <div className="map-tune-actions">
              <button
                onClick={() => { setWeights(Object.fromEntries(WEIGHT_KEYS.map((k) => [k, 5]))) }}
                type="button"
              >Reset to neutral</button>
              <button
                className="btn-primary"
                disabled={saveMutation.isPending}
                onClick={() => saveMutation.mutate(weights)}
              >{saveMutation.isPending ? 'Saving…' : 'Save'}</button>
            </div>
          </aside>
        )}
      </div>
    </div>
  )
}
