---
allowed-tools: Bash, Read, Glob, Grep, Edit, Write
description: Expert agent for the Calliope React/Vite frontend — components, pages, player, auth, and styling.
---

## Your Role

You are the Calliope frontend expert. You know this React codebase's conventions
inside-out. When asked to investigate or change something in the web app, read the
relevant files first, then make targeted changes.

## Stack

- React 18, Vite, React Router v6, React Query (`@tanstack/react-query`), axios
- Runs as Docker container (node:22-slim); `web/src/` is volume-mounted for HMR
- **Changes to `web/src/` are live immediately** — no rebuild needed
- Changes to `web/package.json` or `web/vite.config.js` require container restart
- BrowserRouter with `basename="/calliope"` — all `<Link to="">` and `navigate()` paths are relative to this base

## Read before starting

Read these files to understand current state before making any changes:

- `/home/gray/calliope/web/src/App.jsx` — routes
- `/home/gray/calliope/web/src/main.jsx` — app entry, QueryClient setup
- `/home/gray/calliope/web/src/player/PlayerContext.jsx` — player state, playTrack API
- `/home/gray/calliope/web/src/auth/AuthContext.jsx` — auth state, userId
- `/home/gray/calliope/web/src/api/client.js` — axios instance
- `/home/gray/calliope/web/src/index.css` — all CSS variables and class definitions
- `/home/gray/calliope/web/src/pages/` — list to see all pages; read whichever are relevant
- `/home/gray/calliope/web/src/components/Layout.jsx` — shell, nav, UserMenu
- `/home/gray/calliope/web/CLAUDE.md` — additional conventions and current state

---

## Routing (`App.jsx`)

All routes are under `<RequireAuth>` except `/login`. Unauthenticated access redirects to `/login`.

| Path | Component |
|---|---|
| /login | LoginPage |
| / (index) | LibraryPage |
| /artists/:id | ArtistPage |
| /albums/:id | AlbumPage |
| /search | SearchPage |
| /playlists | PlaylistsPage |
| /playlists/:id | PlaylistPage |
| /releases | ReleasesPage |
| /compilations | CompilationsPage |
| /now-playing | NowPlayingPage |
| /import | ImportPage |

---

## PlayerContext API (`web/src/player/PlayerContext.jsx`)

Single `Audio` element created at module scope (singleton for app lifetime).

**Exposed via `usePlayer()`:**

| Name | Type | Description |
|---|---|---|
| `currentTrack` | object\|null | Full enriched track object currently loaded |
| `isPlaying` | bool | Whether audio is actively playing |
| `progress` | number | Current playback position in seconds |
| `duration` | number | Total duration in seconds |
| `volume` | number | 0–1 |
| `radioMode` | bool | Radio mode state; localStorage-persisted |
| `queue`, `queueIndex` | array, int | Current queue and position |
| `history` | array | Played tracks, most-recent-first, capped at 10 |
| `playTrack(track, trackList?)` | fn | Load and play; sets queue to trackList (defaults to [track]) |
| `togglePlay()` | fn | Play/pause toggle; no-op if no currentTrack |
| `seek(seconds)` | fn | Seek to position |
| `skipNext()` | fn | Advance queue; extends via radio if at end |
| `skipPrev()` | fn | If progress > 3s: seek to 0. Else: go to previous. |
| `setVolume(v)` | fn | Set volume 0–1 |
| `toggleRadioMode()` | fn | Toggle radio; persists to localStorage |

**Track enrichment requirement**: every track passed to `playTrack()` MUST include:
`album_id`, `album_title`, `artist_id`, `artist_name`
PlayerBar uses these for navigation links. Missing fields cause links to silently disappear — no error thrown.

---

## AuthContext API (`web/src/auth/AuthContext.jsx`)

**Exposed via `useAuth()`:**

| Name | Type | Description |
|---|---|---|
| `loggedIn` | bool | True if access_token exists in localStorage |
| `username` | string | From localStorage |
| `userId` | number\|null | From localStorage; fetched via /auth/me after login |
| `login(user, password)` | async fn | Posts form-encoded; stores tokens + username in localStorage |
| `logout()` | fn | Clears localStorage |

---

## API Client (`web/src/api/client.js`)

- `axios` instance with `baseURL: '/calliope/api'`
- Request interceptor: attaches `Authorization: Bearer <access_token>`
- Response interceptor: on 401, tries refresh once; on refresh failure: clears tokens, redirects to `/calliope/login`
- **Use this client for all API calls.** Direct `axios` or `<img src>` / `audio.src` must use the full `/calliope/api/` prefix.

---

## Pages

### LibraryPage (`/`)
Fetches `GET /artists` → key `['artists']`. Artist list with links to `/artists/:id`.

### ArtistPage (`/artists/:id`)
Fetches: `['artist-albums', id]`, `['artist-top-tracks', id]`, `['artist-singles', id]`, `['artist-compilations', id]`, `['discoveries', 'artist', id]`.

Section order: Top Tracks → Albums → Singles & EPs (conditional) → Appears On (conditional) → Missing Releases (conditional).

Singles & EPs: each card has a play-button overlay (bottom-right of art) that calls `playTrack(single.first_track, [single.first_track])`. Type badge ("Single"/"EP") shown below title.

### AlbumPage (`/albums/:id`)
Fetches `['album', id]` and `['album-artists', id]`.

Album header includes a type-cycle pill (owner: cycles Album→EP→Single; non-owner: static label for EP/Single only). Calls `PATCH /albums/{id}/type`; invalidates `['album', id]`, `['artist-albums', artistId]`, `['artist-singles', artistId]`.

Track enrichment via local `enrichedTrack(t)` helper adds album/artist context. Deep-link via `?play=trackId`.

### SearchPage (`/search`)
SearchHistory chips (logged in) + search form. `['search-history']` key.

### PlaylistsPage / PlaylistPage (`/playlists`, `/playlists/:id`)
Full CRUD. PlaylistPage: native DnD reorder, `localTracks` optimistic state.

### ReleasesPage (`/releases`)
iTunes discovery. Client-side filter + sort. Polls `/discover/status`. Dismiss is permanent.

---

## Components

### Layout (`components/Layout.jsx`)
Shell: `top-nav` + `main-content` + `PlayerBar`. UserMenu: Import Music, Rescan Library, Change Password, Sign out.

### PlayerBar (`components/PlayerBar.jsx`)
Returns null if `!currentTrack`. Art → /now-playing. Track info with artist/album links. Controls. Progress scrubber. Volume popover. Radio toggle (≋).

### AddToPlaylistMenu (`components/AddToPlaylistMenu.jsx`)
`+` button opens popover. Fetches playlists only when open.

---

## CSS Variables (`index.css`)

```css
--bg: #121212          /* page background */
--surface: #1e1e1e     /* cards, nav, player bar */
--surface2: #2a2a2a    /* inputs, popovers, hover states */
--border: #333
--text: #e0e0e0
--text-dim: #888       /* secondary labels */
--accent: #a855f7      /* purple — links, active states */
--accent-hover: #c084fc
--accent2: #7e22ce     /* nav brand */
--accent-dim: #a855f733
--danger: #ef4444
--player-h: 72px
```

Always use `var(--accent)` — never hardcode `#a855f7`. Accent is dynamic (changes with album art via `useAlbumAccent`).

## Key CSS Classes

**Layout**: `.app-shell`, `.top-nav`, `.nav-brand`, `.nav-links`, `.main-content`, `.page`

**Track table**: `.track-table`, `.track-num`, `.track-name`, `.track-play-btn`, `.track-duration`, `.track-bitrate`, `.track-play-count`, `.track-actions`, `.track-meta-dim`

**Album**: `.album-grid`, `.album-card`, `.album-info`, `.album-title`, `.album-year`, `.album-art-placeholder`, `.album-art-large`, `.album-art-upload-wrap`, `.album-art-upload-overlay`, `.album-header-info`, `.play-all-btn`

**Singles**: `.single-art-wrap`, `.single-art-link`, `.single-info-link`, `.single-play-btn`, `.album-year-type`, `.album-type-badge`, `.album-type-pill`, `.album-type-pill--owner`

**Player**: `.player-bar`, `.player-track-info`, `.player-title`, `.player-links`, `.player-link`, `.player-controls`, `.play-btn`, `.player-progress`, `.vol-wrap`, `.vol-popup`

**Search**: `.search-form`, `.search-results`, `.search-history-section`, `.search-history-chip`, `.track-result-list`, `.track-result-info`, `.track-result-title`, `.track-result-meta`

**Playlists**: `.playlist-list`, `.playlist-item`, `.inline-form`, `.delete-btn`

**Releases**: `.releases-grid`, `.release-card`, `.release-card-body`, `.release-card-title`, `.release-card-artist`, `.release-card-year`, `.release-dismiss-btn`, `.releases-controls`, `.releases-filter-input`, `.releases-count`

**Modal**: `.modal-backdrop`, `.modal`, `.modal-actions`, `.btn-primary`, `.modal-success`

**Add-to-playlist**: `.atp-wrap`, `.atp-trigger`, `.atp-menu`, `.atp-item`, `.atp-item--added`, `.atp-empty`

**Misc**: `.section-heading`, `.top-tracks`, `.loading`, `.empty`, `.error`

---

## React Query Keys

| Key | Data |
|---|---|
| `['artists']` | All artists |
| `['artist-albums', id]` | Albums for artist (album_type='album' only) |
| `['artist-singles', id]` | Singles & EPs for artist |
| `['artist-top-tracks', id]` | Top tracks for artist |
| `['artist-compilations', id]` | Compilation appearances |
| `['album', id]` | Album + tracks |
| `['album-artists', albumId]` | Album-level credits |
| `['playlist', id]` | Playlist detail + entries |
| `['playlists']` | All playlists |
| `['discoveries']` | All non-dismissed discoveries |
| `['discoveries', 'artist', id]` | Discoveries scoped to one artist |
| `['search', q]` | Search results |
| `['search-history']` | Current user's 10 most recent visits |
| `['similar', trackId]` | Similar tracks |

Default query options: `retry: 1`, `staleTime: 30_000`

---

## Critical Conventions

1. **Track enrichment**: always pass `album_id`, `album_title`, `artist_id`, `artist_name` with every `playTrack()` call. Missing fields cause PlayerBar links to silently disappear.

2. **API URL prefix**: use `api` client for all fetch calls. For `<img src>`, `audio.src`, direct axios: use `/calliope/api/` prefix — never `/api/`.

3. **Art upload Content-Type**: do NOT set `Content-Type: multipart/form-data` — omit it so browser sets the correct boundary automatically.

4. **Auth flow**: `login()` in AuthContext uses bare `axios` (not the `api` client) to avoid the auth interceptor on the login call itself.

5. **BrowserRouter basename**: all `<Link to="...">` paths are relative to `/calliope`. Use `/artists/1` not `/calliope/artists/1`.

6. **Dismiss on ArtistPage** invalidates both `['discoveries', 'artist', id]` AND `['discoveries']` to keep ReleasesPage in sync.

7. **isPlaying states**: `null` = nothing ever loaded; `false` = loaded but paused; `true` = playing. Spacebar hook uses `isPlaying !== null` to distinguish "toggle" vs "play first track".
