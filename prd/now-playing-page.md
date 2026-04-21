# PRD: Now Playing Page

## Goal

A full-screen view of the current track — big art, wide scrubber, and context:
what just played, what's coming next, and what sounds similar. The destination
when you want to focus on the music rather than browse the library.

---

## Navigation

- **Entry points**: clicking the album art thumbnail in `PlayerBar`, or clicking
  the "Calliope" logo in the top-left of the nav, both navigate to
  `/calliope/now-playing`
- **Exit**: browser back, or clicking any nav link in the top nav
- **Empty state**: if nothing is playing, show a centered muted message —
  "Nothing playing" — with a link back to the library

---

## Layout

Two-column layout, vertically centered on the page.

```
┌───────────────────────────────────────────────────────────────┐
│                         │                                      │
│   [Album Art]           │  Played                             │
│   (large, square,       │  ─────────────────────              │
│    ~40vmin)             │  · Track A — Artist                 │
│                         │  · Track B — Artist                 │
│   Track Title           │                                      │
│   Artist · Album · Year │  Now Playing                        │
│                         │  ─────────────────────              │
│   [═══════════════════] │  ▶ Current Track — Artist           │
│   0:42           3:21   │                                      │
│                         │  Up Next                            │
│   ⏮   ⏪   ⏯   ⏩   ⏭  │  ─────────────────────              │
│   🔊──────  📻          │  · Track C — Artist                 │
│                         │  · Track D — Artist                 │
│                         │                                      │
│                         │  Similar                            │
│                         │  ─────────────────────              │
│                         │  · Track E — Artist · Album         │
│                         │  · Track F — Artist · Album         │
│                         │  · Track G — Artist · Album         │
│                         │  · Track H — Artist · Album         │
│                         │  · Track I — Artist · Album         │
└───────────────────────────────────────────────────────────────┘
```

### Left column

- Album art: large square image, same source as `GET /albums/{id}/art`, roughly
  `40vmin` — fills the column without overflowing on typical screens
- Track title: large, bold
- Artist name (links to artist page) · Album title (links to album page) · Year
- Scrubber: full column width, same behavior as `PlayerBar` scrubber but wider and
  taller hit target
- Elapsed / remaining timestamps flanking the scrubber
- Playback controls: prev, back 15s, play/pause, forward 15s, next — same as
  `PlayerBar`
- Volume slider (horizontal)
- Radio mode toggle (same icon as `PlayerBar`)

The `PlayerBar` at the bottom of the screen is still visible on this page — the
left column is a larger mirror of it, not a replacement.

### Right column

Three sections stacked vertically, separated by a muted label + divider.

#### Played (2 tracks)
The two tracks most recently played before the current one, oldest first (so reading
top-to-bottom is chronological). Sourced from `PlayerContext` queue history.
Each row: track title + artist name. Clicking navigates to the album page.
Muted styling — these are in the past.

#### Now Playing (1 track)
The current track, accent-colored, with a small animated equalizer icon to the left.
Non-interactive (you're already here).

#### Up Next (2 tracks)
The next two tracks in the queue. Sourced from `PlayerContext` queue. If radio mode
is on and the queue has fewer than 2 remaining, show a muted "Radio will continue…"
note in place of missing slots — radio picks the next track only when the current one
ends, so future radio picks aren't known yet.

#### Similar (5 tracks)
Tracks returned by `GET /tracks/{id}/similar?limit=5` for the current track.
Each row: track title · artist name · album title. Clicking plays the track
immediately (same as clicking a track anywhere in the app).

If the current track has no vector yet (not indexed), the section is hidden entirely
— no error, no placeholder. It will appear naturally once a rescan with indexing runs.

Similarity results are fetched fresh each time the current track changes.

---

## Implementation

### New files
- `web/src/pages/NowPlayingPage.jsx`
- Route: `/calliope/now-playing` added to the router

### `PlayerContext.jsx` additions
- `history`: array of the last N tracks played (prepend on `onended` or manual skip);
  cap at 10 — the page only shows 2 but keeping more allows future use
- `queue`: already exists; expose `upNext` as the slice starting at current index + 1

### `PlayerBar.jsx`
- Album art thumbnail becomes a `<Link to="/calliope/now-playing">` (or `useNavigate`
  on click)

### `NowPlayingPage.jsx`
- Reads `currentTrack`, `history`, `upNext`, `isPlaying`, `togglePlayPause`,
  `seek`, `volume`, `radioMode`, `toggleRadioMode` from `PlayerContext`
- Fetches `GET /albums/{album_id}/art` for the large image (already cached by browser
  from album page visits)
- Fetches `GET /tracks/{id}/similar?limit=5` via React Query, keyed on
  `['similar', currentTrack.id]`; disabled when `currentTrack` is null

### CSS additions (`index.css`)
- `.now-playing-page` — two-column grid layout
- `.now-playing-art` — square image, `~40vmin`
- `.now-playing-scrubber` — wider/taller than PlayerBar version
- `.now-playing-queue-section` — label + divider + track list
- `.now-playing-queue-track` — single track row in the queue panel
- `.now-playing-similar-track` — single track row in the similar panel
- `.now-playing-equalizer` — small animated bars icon for current track indicator

---

## Out of Scope

- "Add to queue" or "Play next" action on similar tracks (clicking plays immediately)
- Lyrics display
- Fullscreen / kiosk mode
- Responsive / mobile layout (desktop only for now)
- Showing more than 5 similar tracks (no pagination)
