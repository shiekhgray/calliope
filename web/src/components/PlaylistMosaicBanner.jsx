import { useEffect, useRef, useState } from 'react'

const ROWS = 3
const CELL = 56
const GAP = 3
const STRIDE = CELL + GAP

function fillProb(c, C) {
  // Squared exponential: early columns near-certain, rapid falloff after midpoint
  const x = c / C
  return Math.exp(-4 * x * x)
}

function computeLayout(tracks, cols) {
  if (!tracks.length || cols < 1) return []

  const counts = {}
  const firstPos = {}
  for (let i = 0; i < tracks.length; i++) {
    const id = tracks[i].album_id
    if (!id) continue
    const key = String(id)
    counts[key] = (counts[key] ?? 0) + 1
    if (firstPos[key] === undefined) firstPos[key] = i
  }

  const sorted = Object.keys(counts).sort((a, b) => {
    const diff = counts[b] - counts[a]
    return diff !== 0 ? diff : firstPos[a] - firstPos[b]
  })

  if (!sorted.length) return []

  const largeCount = Math.min(Math.ceil(sorted.length * 0.25), 3)
  const large = new Set(sorted.slice(0, largeCount))

  // Col 0 is always fully active; remaining columns use exponential decay
  const active = Array.from({ length: ROWS }, () =>
    Array.from({ length: cols }, (_, c) =>
      c === 0 ? true : Math.random() < fillProb(c, cols)
    )
  )
  const occ = Array.from({ length: ROWS }, () => new Array(cols).fill(false))

  const placed = []

  for (const albumId of sorted) {
    const isLarge = large.has(albumId) && cols >= 2

    if (isLarge) {
      // Column-first: find leftmost column that has a free 2×2 block
      loop: for (let c = 0; c <= cols - 2; c++) {
        for (let r = 0; r <= ROWS - 2; r++) {
          if (
            active[r][c] && !occ[r][c] &&
            active[r][c + 1] && !occ[r][c + 1] &&
            active[r + 1][c] && !occ[r + 1][c] &&
            active[r + 1][c + 1] && !occ[r + 1][c + 1]
          ) {
            placed.push({ albumId, col: c + 1, row: r + 1, size: 2 })
            occ[r][c] = occ[r][c + 1] = occ[r + 1][c] = occ[r + 1][c + 1] = true
            break loop
          }
        }
      }
    } else {
      // Column-first: fill each column top-to-bottom before moving right
      let found = false
      loop: for (let c = 0; c < cols; c++) {
        for (let r = 0; r < ROWS; r++) {
          if (active[r][c] && !occ[r][c]) {
            placed.push({ albumId, col: c + 1, row: r + 1, size: 1 })
            occ[r][c] = true
            found = true
            break loop
          }
        }
      }
      if (!found) break
    }
  }

  return placed
}

export default function PlaylistMosaicBanner({ tracks }) {
  const [cols, setCols] = useState(() => Math.max(1, Math.floor(window.innerWidth / STRIDE)))
  const [layout, setLayout] = useState([])
  const tracksRef = useRef(tracks)
  tracksRef.current = tracks

  useEffect(() => {
    const onResize = () => setCols(Math.max(1, Math.floor(window.innerWidth / STRIDE)))
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // Stable identity: sorted unique album IDs as a string.
  // PlaylistPage re-renders on every audio progress tick (consumes PlayerContext),
  // which would create a new tracks array reference each time and reshuffle the
  // layout. Using a derived string means the effect only fires when the actual
  // album composition changes, not on every render.
  const albumSig = tracks?.length
    ? [...new Set(tracks.map(t => t.album_id).filter(Boolean))].sort().join(',')
    : ''

  useEffect(() => {
    setLayout(albumSig ? computeLayout(tracksRef.current, cols) : [])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [albumSig, cols])

  if (!tracks?.length) return null

  return (
    <div
      className="mosaic-banner"
      style={{ gridTemplateColumns: `repeat(${cols}, ${CELL}px)` }}
    >
      {layout.map((item) => (
        <img
          key={item.albumId}
          src={`/calliope/api/albums/${item.albumId}/art`}
          alt=""
          style={{
            gridColumn: `${item.col} / span ${item.size}`,
            gridRow: `${item.row} / span ${item.size}`,
          }}
          onError={(e) => { e.currentTarget.style.display = 'none' }}
        />
      ))}
    </div>
  )
}
