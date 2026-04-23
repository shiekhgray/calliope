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

## Current Codebase

App entry: !`cat -n /home/gray/calliope/web/src/main.jsx`
Routes: !`cat -n /home/gray/calliope/web/src/App.jsx`
PlayerContext: !`cat -n /home/gray/calliope/web/src/player/PlayerContext.jsx`
AuthContext: !`cat -n /home/gray/calliope/web/src/auth/AuthContext.jsx`
API client: !`cat -n /home/gray/calliope/web/src/api/client.js`
Layout: !`cat -n /home/gray/calliope/web/src/components/Layout.jsx`
PlayerBar: !`cat -n /home/gray/calliope/web/src/components/PlayerBar.jsx`
AddToPlaylistMenu: !`cat -n /home/gray/calliope/web/src/components/AddToPlaylistMenu.jsx`
ChangePasswordModal: !`cat -n /home/gray/calliope/web/src/components/ChangePasswordModal.jsx`
Pages: !`ls /home/gray/calliope/web/src/pages/`
Hooks: !`ls /home/gray/calliope/web/src/hooks/ 2>/dev/null || echo "(none yet)"`
CSS: !`cat -n /home/gray/calliope/web/src/index.css`
Vite config: !`cat -n /home/gray/calliope/web/vite.config.js`

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

`RequireAuth` is a simple wrapper: if `!loggedIn`, renders `<Navigate to="/login" replace />`.

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
| `playTrack(track, trackList?)` | fn | Load and play a track; sets queue to trackList (defaults to [track]); requires enriched track |
| `togglePlay()` | fn | Play/pause toggle; no-op if no currentTrack |
| `seek(seconds)` | fn | Seek to position |
| `skipNext()` | fn | Advance to next in queue |
| `skipPrev()` | fn | If progress > 3s: seek to 0. Else: go to previous in queue. |
| `setVolume(v)` | fn | Set volume 0–1 |

**Internal behavior:**
- `onended`: fires `POST /tracks/{id}/played` (fire-and-forget, errors swallowed), then auto-advances queue
- `ontimeupdate`: updates `progress` state
- `ondurationchange`: updates `duration` state
- Queue is `[track, ...]`; `queueIndex` tracks current position
- `playTrack(track, trackList)`: finds track in list by id; if not found, uses index 0

**Track enrichment requirement**: every track passed to `playTrack()` MUST include:
`album_id`, `album_title`, `artist_id`, `artist_name`
PlayerBar uses these for navigation links. Missing fields cause links to silently disappear — no error thrown.

---

## AuthContext API (`web/src/auth/AuthContext.jsx`)

**Exposed via `useAuth()`:**

| Name | Type | Description |
|---|---|---|
| `loggedIn` | bool | True if access_token exists in localStorage |
| `username` | string | From localStorage; recovered via GET /auth/me if missing |
| `login(user, password)` | async fn | Posts form-encoded to `/calliope/api/auth/login`; stores tokens + username in localStorage |
| `logout()` | fn | Clears localStorage tokens + username |

On mount: if `loggedIn && !username`, calls `GET /auth/me` to recover username (handles pre-existing sessions after deploys that added username storage).

---

## API Client (`web/src/api/client.js`)

- `axios` instance with `baseURL: '/calliope/api'`
- Request interceptor: attaches `Authorization: Bearer <access_token>` from localStorage
- Response interceptor: on 401, tries refresh once (`POST /calliope/api/auth/refresh` with refresh_token), retries original request. On refresh failure: clears tokens, redirects to `/calliope/login`.
- **Use this client for all API calls.** Direct `axios` (not the `api` instance) or `<img src>` / `audio.src` must use the full `/calliope/api/` prefix.

---

## Pages

### LibraryPage (`/`)
Fetches `GET /artists` → React Query key `['artists']`. Renders artist list with links to `/artists/:id`.

### ArtistPage (`/artists/:id`)
Fetches:
- `GET /artists/{id}/albums` → key `['artist-albums', id]`
- `GET /artists/{id}/top-tracks` → key `['artist-top-tracks', id]`
- `GET /discover?artist_id={id}` → key `['discoveries', 'artist', id]`

Renders: artist name (from `albums[0].artist_name`), Top Tracks table (always shown, even if 0 plays), Albums grid, Missing Releases section (only if non-empty).

Missing Releases: reuses `.releases-grid` / `.release-card` CSS. Dismiss button only shown when `loggedIn`. Dismiss invalidates both `['discoveries', 'artist', id]` and `['discoveries']` to keep ReleasesPage in sync.

Album art: `<img src="/calliope/api/albums/{id}/art">` — hardcoded prefix, not through `api` client.

### AlbumPage (`/albums/:id`)
Fetches `GET /albums/{id}` → key `['album', id]`.

Enriches tracks with album context via local `enrichedTrack(t)` helper that adds `album_title`, `album_id`, `artist_id`, `artist_name`.

Album art: hover overlay for upload. Click triggers hidden `<input type="file">`. Upload via `api.put('/albums/${id}/art', form)` — do NOT set Content-Type manually, let browser set boundary. Cache-busts displayed image with `?v=${artVersion}` local state after upload.

Track table: double-click or play button starts playback. Active row has class `active` and `.track-name` turns accent color. Shows bitrate (muted) and play_count (blank when 0).

### SearchPage (`/search`)
Two-part: `SearchHistory` component (shown when logged in + history non-empty) above the search form.

`SearchHistory`: fetches `GET /search/history` → key `['search-history']`, enabled only when loggedIn. Chips navigate (artist/album) or play (track) and fire `POST /search/history` + invalidate `['search-history']`.

Search: controlled input, submits on form submit. `GET /search?q=` → key `['search', submitted]`, disabled when submitted is empty. Results: artist links fire recordHistory + navigate. Album clicks fire recordHistory + navigate. Track play buttons fire recordHistory + playTrack.

### PlaylistsPage (`/playlists`)
Fetches `GET /playlists` → key `['playlists']`. Create (inline form toggle) and delete mutations. No auth guard on fetching; mutations use authed API client.

### PlaylistPage (`/playlists/:id`)
Fetches `GET /playlists/{id}` → key `['playlist', id]`.

Drag-and-drop reorder: native HTML5 DnD. `localTracks` state holds optimistic order during drag. On drop: updates `localTracks`, fires `PUT /playlists/{id}/tracks/reorder`. On API error: resets `localTracks` to null (reverts to server state). `onSuccess` of fresh fetch also resets `localTracks`.

Track objects from entries already include `album_id`, `album_title`, `artist_id`, `artist_name` — no enrichment needed. `entry_id` used as React key (not track.id, since same track can appear multiple times).

Rename: inline form replaces title on edit. Removes track: `DELETE /playlists/{id}/tracks/{track_id}`.

### ReleasesPage (`/releases`)
Fetches `GET /discover` → key `['discoveries']`. Polls `/discover/status` on mount to seed `lastRefreshed` and detect in-progress refresh.

Client-side filter + sort via `useMemo`: text filter (artist name or album title, case-insensitive substring), sort by Artist A–Z / Newest / Oldest. "Showing X of Y" count only shown when filter active.

Refresh: posts `/discover/refresh`, then polls `/discover/status` every 2s. Handles 409 gracefully (already running → start polling). After completion: invalidates `['discoveries']`, shows "Up to date" for 3s.

Dismiss: sets dismissed permanently. Dismissed entries never shown again even after refresh.

---

## Components

### Layout (`components/Layout.jsx`)
Shell: `top-nav` + `main-content` (scrollable) + `PlayerBar`. Nav links: Library, Search, Playlists, Releases. Brand: `<span className="nav-brand">Calliope</span>` (not a link currently).

`UserMenu`: dropdown with Rescan Library, Change Password, Sign out. Rescan polls `/scanner/status` every 2s; handles 409. "Scan complete" shown in accent for 3s. Outside-click closes via mousedown listener.

### PlayerBar (`components/PlayerBar.jsx`)
Returns null if `!currentTrack`. Three-column grid: track info (title + artist/album links) | controls (prev/play/next) | progress (elapsed/scrubber/total + volume).

Links only render when all required enrichment fields are present (no fallback text). Volume: popover with vertical range slider.

### AddToPlaylistMenu (`components/AddToPlaylistMenu.jsx`)
`+` button opens popover. Fetches `['playlists']` only when open. Click adds track, shows "✓ Added" for 800ms, then closes.

### ChangePasswordModal (`components/ChangePasswordModal.jsx`)
Posts `POST /auth/change-password` with `{current_password, new_password}`. Client-side confirm match check. Shows success state after completion.

---

## CSS Variables (`index.css`)

```css
--bg: #121212          /* page background */
--surface: #1e1e1e     /* cards, nav, player bar */
--surface2: #2a2a2a    /* inputs, popovers, hover states */
--border: #333
--text: #e0e0e0
--text-dim: #888       /* secondary labels, muted info */
--accent: #a855f7      /* purple — links, active states, buttons */
--accent-hover: #c084fc
--danger: #ef4444      /* delete buttons, errors */
--player-h: 72px       /* player bar height; used in main-content padding-bottom */
```

Always use `var(--accent)` — never hardcode `#a855f7`. The accent will become dynamic (dynamic-theme PRD).

## Key CSS Classes

**Layout**: `.app-shell`, `.top-nav`, `.nav-brand`, `.nav-links`, `.main-content`, `.page`

**Track table**: `.track-table`, `.track-num`, `.track-name`, `.track-play-btn`, `.track-duration`, `.track-bitrate`, `.track-play-count`, `.track-actions`, `.track-drag`, `.track-meta-dim`

**Album**: `.album-grid`, `.album-card`, `.album-art-placeholder`, `.album-art-large`, `.album-art-upload-wrap`, `.album-art-upload-overlay`, `.album-header-info`, `.play-all-btn`

**Player**: `.player-bar`, `.player-track-info`, `.player-title`, `.player-links`, `.player-link`, `.player-controls`, `.play-btn`, `.player-progress`, `.vol-wrap`, `.vol-popup`

**Search**: `.search-form`, `.search-results`, `.search-history-section`, `.search-history-label`, `.search-history-grid`, `.search-history-chip`, `.track-result-list`, `.track-result-info`, `.track-result-title`, `.track-result-meta`

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
| `['artist-albums', id]` | Albums for artist |
| `['artist-top-tracks', id]` | Top 10 tracks for artist |
| `['album', id]` | Album + tracks |
| `['playlist', id]` | Playlist detail + entries |
| `['playlists']` | All playlists |
| `['discoveries']` | All non-dismissed discoveries |
| `['discoveries', 'artist', id]` | Discoveries scoped to one artist |
| `['search', q]` | Search results for query q |
| `['search-history']` | Current user's 10 most recent history entries |
| `['similar', trackId]` | Similar tracks (radio mode — not yet built) |

Default query options (main.jsx): `retry: 1`, `staleTime: 30_000`

---

## Critical Conventions

1. **Track enrichment**: always pass `album_id`, `album_title`, `artist_id`, `artist_name` with every `playTrack()` call. Missing fields cause PlayerBar links to silently disappear.

2. **API URL prefix**: use `api` client (baseURL `/calliope/api`) for all fetch calls. For hardcoded URLs in JSX (`<img src>`, `audio.src`, direct axios): use `/calliope/api/` prefix — never `/api/`. Forgetting this causes silent failures.

3. **Art upload Content-Type**: do NOT set `Content-Type: multipart/form-data` on axios PUT — omit it entirely so browser sets the correct boundary automatically.

4. **Play count is fire-and-forget**: `POST /tracks/{id}/played` errors are swallowed. `onended` fires only on natural completion, not on skip.

5. **Auth flow**: `login()` in AuthContext uses bare `axios` (not the `api` client) to avoid the auth interceptor on the login call itself.

6. **Vite proxy**: `/calliope/api` → `process.env.API_URL || http://localhost:8000` (strips `/calliope/api` prefix). In Docker: `API_URL=http://api:8000`. `allowedHosts` includes `dresdengray.com`.

7. **BrowserRouter basename**: all `<Link to="...">` paths are relative to `/calliope`. Use `/artists/1` not `/calliope/artists/1` in Link and navigate().

8. **Dismiss on ArtistPage** invalidates both `['discoveries', 'artist', id]` AND `['discoveries']` to keep ReleasesPage in sync.
