# PRD: Playlist Mosaic Banner

## Goal

Replace the blank space at the top of the playlist detail page with a full-width
hero mosaic of album art drawn from the playlist's tracks. Art squares are dense
on the left and thin out progressively toward the right. Some albums appear as
oversized 2×2 squares based on how many of their tracks are in the playlist.
Behind the sparse cells, a dark-to-transparent gradient creates depth and
transitions naturally into the page background.

## Visual Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ░░ ▓▓▓▓ ░░ ▓▓▓▓ ▓▓ ▓▓ ░░   ▓▓    ░░       ░░               │  ~200px tall │
│ ░░ ▓▓▓▓ ░░ ▓▓▓▓ ▓▓ ▓▓ ░░   ▓▓                                             │
│ ░░ ░░░░ ░░ ▓▓ ▓▓ ▓▓ ░░      ░░                                            │
└────────── dark ──────────────────────────── → transparent ─────────────────┘
```

- `▓▓` = album art cells (1×1 or 2×2)
- `░░` = empty cells (show the gradient background)
- Left ~40% of the banner: near-fully packed with art
- Middle ~40%: art thins out — randomly missing cells and columns
- Right ~20%: very sparse, fading to nothing

The banner sits **above** the playlist title, description, and track list. It
spans the full page width with no horizontal padding. The rest of the playlist
content remains below it unchanged.

## Grid Specification

| Property | Value |
|---|---|
| Cell size | 56 px |
| Gap between cells | 3 px |
| Row count | Fixed: 3 rows |
| Banner height | `(3 × 56) + (2 × 3)` = 174 px (close to ~200 px target) |
| Column count | `floor(viewportWidth / 59)` — computed on mount and on resize |
| Background | `linear-gradient(to right, #0e0e0e 0%, transparent 90%)` |

Cells are square with no border-radius. A 2×2 cell spans 2 columns and 2 rows
(`grid-column: span 2; grid-row: span 2`), sized to `(2 × 56) + (1 × 3)` =
115 px per side.

## Album Selection & Sizing

### Step 1 — Count album frequencies

From the playlist's track list (already available in the detail page response),
count how many tracks each unique `album_id` contributes.

```js
const albumCounts = {};
for (const track of tracks) {
  albumCounts[track.album_id] = (albumCounts[track.album_id] ?? 0) + 1;
}
// Sort descending: [[album_id, count], ...]
const sorted = Object.entries(albumCounts).sort((a, b) => b[1] - a[1]);
```

### Step 2 — Assign sizes

Albums in the top tier (highest track count) earn a 2×2 slot. Threshold:

```js
const largeCount = Math.min(Math.ceil(sorted.length * 0.25), 3);
const large = new Set(sorted.slice(0, largeCount).map(([id]) => id));
```

- `largeCount` is capped at 3 — at most three 2×2 squares in the banner.
- If all albums have identical counts (e.g. all exactly 1), no 2×2 squares are
  assigned (top 25% rounds down to 0 for small playlists — acceptable).

### Step 3 — Build the ordered album list

Preserve frequency order (desc). Within a tie, preserve playlist positional order
(first occurrence of the album in the track list wins). This list drives packing.

## Grid Packing Algorithm (client-side)

Runs in the component on mount (no API changes needed).

### Density curve

For a grid with `C` total columns, the fill probability for column index `c`
(0-based, left to right):

```js
function fillProbability(c, C) {
  const x = c / C;           // normalized position 0.0 → 1.0
  return Math.max(0, 1 - Math.pow(x, 0.55));
}
```

This gives ~100% probability at `c=0`, ~50% around the midpoint, and ~0% near
the right edge. The exponent 0.55 produces a convex curve — slow falloff on the
left, steep falloff on the right.

### Slot generation

Build a 3×C boolean matrix of "active" slots by sampling each cell:

```js
function buildActiveMatrix(rows, cols) {
  return Array.from({ length: rows }, (_, r) =>
    Array.from({ length: cols }, (_, c) => Math.random() < fillProbability(c, cols))
  );
}
```

Column 0 is always 100% filled (clamp keeps it at 1.0).

### Packing

Iterate the ordered album list. For each album:

1. If the album is **large (2×2)**: scan active cells left-to-right, top-to-bottom
   for the top-left corner of a free 2×2 block. A 2×2 block is free when all four
   cells `[r][c], [r][c+1], [r+1][c], [r+1][c+1]` are active and unoccupied.
   Place the album there and mark all four cells occupied.

2. If the album is **small (1×1)**: scan for the first active, unoccupied cell.
   Place the album there and mark it occupied.

3. If no valid slot remains for an album (the active matrix is fully consumed),
   stop — do not render remaining albums.

Albums that have no `cover_art_path` are skipped entirely (treated as if not in
the list).

### Output

The packing produces a flat list of placed items:

```js
[
  { albumId, coverArtPath, col, row, size: 1 | 2 },
  ...
]
```

This drives the CSS grid render. The rest of the grid is the gradient background.

## Component

**`PlaylistMosaicBanner.jsx`** — new component, imported by `PlaylistPage.jsx`.

Props:
```
tracks: Array<{ album_id, album_title, cover_art_path, ... }>
```

The component:
- Derives `windowWidth` via a `resize` listener (or `ResizeObserver`)
- Recomputes the layout whenever `tracks` or `windowWidth` changes
- Renders a `<div className="mosaic-banner">` with `display: grid`
- Each placed item is an `<img>` with `onError={() => img.style.display='none'}`
- 2×2 images use `grid-column: span 2; grid-row: span 2`

Since "recompute on load" is the desired behavior, no seed is applied to the
random number generator — each page load produces a fresh layout. This is the
correct behavior for a small playlist where the same art would show each time
anyway, and gives variety on large playlists.

## CSS

```css
.mosaic-banner {
  width: 100%;
  height: 174px;
  background: linear-gradient(to right, #0e0e0e 0%, transparent 90%);
  overflow: hidden;
  display: grid;
  grid-template-rows: repeat(3, 56px);
  /* grid-template-columns set inline: repeat(C, 56px) */
  gap: 3px;
  align-items: start;
}

.mosaic-banner img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
```

`grid-template-columns` is set as an inline style because the column count is
dynamic (`repeat(${cols}, 56px)`).

## Page Integration

In `PlaylistPage.jsx`, render `<PlaylistMosaicBanner>` as the first child of the
page container, before the existing title/description/track list sections. No
layout changes needed to the rest of the page.

If the playlist has zero tracks (empty playlist), render nothing (return `null`
from the component).

## Edge Cases

| Scenario | Behavior |
|---|---|
| Playlist has 0 tracks | Banner not rendered |
| Playlist has 1 unique album | One 2×2 square placed at far left; rest of banner is gradient |
| All albums have art missing | Banner renders as pure gradient |
| Viewport very narrow (<300px) | `cols` may be 4–5; packing still works, density just reaches zero quickly |
| Same album appears in 2×2 and would also fill 1×1 slots | Each album is placed exactly once — no duplicates |

## Out of Scope

- Server-side computation (all logic is client-side)
- Caching or seeding the layout across visits
- Animation or transition effects on the mosaic cells
- Hover effects on individual cells
- Linking cells to the album page
- Adjusting cell size for mobile (fixed 56px)
- Showing the banner on the playlists list page (covered by playlist-cards.md)
