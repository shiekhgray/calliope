# Web App — Calliope Frontend

React + Vite. Runs as Docker container. `./web/src` is volume-mounted — edit on host, HMR reloads instantly. No rebuild needed for frontend changes.

## Structure

```
web/src/
  api/client.js             ← axios; Bearer token; auto-refresh on 401; baseURL = '/calliope/api'
  auth/
    AuthContext.jsx          ← loggedIn, username, userId, login(), logout(); username + user_id in localStorage; userId fetched via /auth/me after login
    LoginPage.jsx            ← reads ?redirect= param, navigates there after login
  hooks/
    useAlbumAccent.js        ← Vibrant palette → 3 CSS var tiers; JS sRGB animation
    useSpacebarPlayback.js   ← global spacebar toggle + per-page first-track registration
  player/
    PlayerContext.jsx        ← singleton Audio; queue, play/pause, seek, volume, radio mode, history
  components/
    Layout.jsx               ← nav + player shell; owns spacebar listener; "Calliope" links /now-playing
    PlayerBar.jsx            ← fixed bottom bar; art thumbnail → /now-playing; ≋ radio toggle
    AddToPlaylistMenu.jsx    ← "+" popover on every track row
    ChangePasswordModal.jsx
    SimilarityWeightsModal.jsx  ← 3 groups × 3 sliders; PUT /auth/similarity-weights; opened from user menu "Sound Matching"
    RadioModesModal.jsx         ← radio-group of 4 continuation modes + Variety slider; PUT /auth/radio-settings; opened from user menu "Radio Modes"
    PlaylistMosaicBanner.jsx    ← full-width 174px hero above PlaylistPage content; bin-packs album art left→right with squared-exponential density; col-first scan; top-25% albums get 2×2 slots
    ReleaseCardGenres.jsx       ← "Genres" toggle button + chip display for discovery cards; used in both ReleasesPage and ArtistPage (Missing Releases section)
  pages/
    LibraryPage              ← artist list
    ArtistPage               ← top 10 tracks + albums grid + Singles & EPs section + "Appears On" (compilations) + Missing Releases
    AlbumPage                ← album header (art upload overlay) + track table + share links; owner-only type-cycle pill (album→ep→single)
    SearchPage               ← search + history chips
    PlaylistsPage            ← playlist cards (2×2 art collage, track preview, genre chips, hover-reveal delete); PlaylistCard component inline
    PlaylistPage             ← detail + remove/reorder tracks; mosaic banner above page header
    ReleasesPage             ← iTunes discovery; filter + sort; dismiss per card
    NowPlayingPage           ← /now-playing; large art, scrubber, queue context, similar tracks
    CompilationsPage         ← /compilations; VA album grid
    ImportPage               ← /import; drag-and-drop zip; Bandcamp + Amazon + Qobuz zips; loose MP3/M4A/FLAC singles (FLAC transcoded server-side); progress bar
    MapPage                  ← /map; Music Map. Canvas 2-D scatter (no regl/webgl dep — chosen to avoid a container rebuild; smooth at ~3k pts). Pan (drag) / zoom (wheel) / hover tooltip w/ lazy album art / click-to-play. Lens selector: Clusters (stored cluster_id, or live recolor) / Single feature (viridis ramp via /map/lens) / 3-PC gestalt (/map/pca rgb). "Tune weights" panel embeds the Sound Matching sliders → debounced GET /map/clusters?weighted&w= live recolor; Save → PUT /auth/similarity-weights. Now-playing track + /similar neighbors highlighted (ring + dim others).
```

## Key Conventions

**API URLs**: anything not going through the axios client (img src, audio.src, direct fetch) must use `/calliope/api/` prefix. The axios client already has `baseURL: '/calliope/api'`. Missing prefix = silent failure (images don't load, audio doesn't play).

**Track enrichment**: `playTrack()` requires `album_id`, `album_title`, `artist_id`, `artist_name`. Missing fields silently drop PlayerBar links — no error, no fallback text.

**isPlaying states**: `null` = nothing ever loaded; `false` = loaded but paused; `true` = playing. Important for spacebar hook: `isPlaying !== null` means "something is loaded, toggle it" vs "play first track on this page".

**Vite proxy**: `/calliope/api` → `http://api:8000` (Docker env) or `http://localhost:8000` (local). Strips the prefix before forwarding to the API.

**Album art upload**: do NOT manually set `Content-Type: multipart/form-data` on the axios PUT — omit it and let the browser set it with the correct boundary automatically.

**PlayerContext re-render hazard**: `PlaylistPage` (and any page that calls `usePlayer()`) re-renders on every audio progress tick because the context value object is recreated each second. Any derived array created inline (e.g. `playlist.entries.map(...)`) gets a new reference every render. Components that key a `useEffect` on such an array will re-fire every second. Fix: derive a stable primitive (e.g. sorted unique IDs joined as a string) and use that as the effect dep instead of the array reference. See `PlaylistMosaicBanner` for the pattern.

## PlayerContext API

```js
{
  currentTrack,           // track object or null
  isPlaying,              // null | false | true
  queue, queueIndex,      // current queue array + position
  history,                // played tracks, most-recent-first, capped at 10
  radioMode,              // bool; localStorage-persisted; default on
  toggleRadioMode(),
  playTrack(track),       // replaces queue with single track
  playQueue(tracks, idx), // replaces queue, starts at idx
  skipNext(), skipPrev(),
  seek(seconds),
  setVolume(0–1),
}
```

- `history` is pushed on `onended` and `skipNext`; reset on `playTrack`
- Radio mode extends the queue when it empties (via `onended`) or `skipNext` is called at end of queue
- **Radio continuation algorithm**: `_extendWithRadio` POSTs `/radio/next` (not `/tracks/{id}/similar`). The selected mode + variety come from `['me']` (`radio_mode`/`radio_variety`), mirrored into `radioAlgoRef`/`radioVarietyRef`. Session state held in refs: `anchorRef` (track that started the station — pinned on the first extension after a manual play), `sourceAlbumRef` (album excluded from radio), `radiusRef` (ripple state echoed to/from the server). All three reset in `playTrack`. The on/off toggle (`radioModeRef`/localStorage) is unchanged.
- `onended` fires POST `/tracks/{id}/played` — fire-and-forget, errors swallowed
- **StrictMode + nested setState hazard**: `<StrictMode>` double-invokes functional updaters. Calling `setState` inside another `setState`'s updater causes the inner dispatch to fire twice, with React processing both sequentially. In `onended` this meant `queueIndex` incremented by 2 (skipping every other track). Fix: `queueRef`/`queueIndexRef`/`currentTrackRef` mirror state; all event handlers read refs and call flat (non-nested) setters via `_setQueue`/`_setQueueIndex`/`_setCurrentTrack` wrappers.
- **Tab discard survival**: `PlayerContext` holds a Web Lock (`navigator.locks`, `'calliope-player'`) to hint Chrome not to discard the tab. State is also saved to `sessionStorage` (`'calliope-player-state'`) on `visibilitychange`/`pagehide` and restored on mount — audio src is reloaded and seeks to saved position, `isPlaying` is set to `false` (not `null`) so PlayerBar renders. `playTrack()` clears saved state to prevent stale restore racing a fresh play.

## Dynamic Color Theme

Three CSS variables updated on every track change:

| Variable | Value | Used for |
|---|---|---|
| `--accent` | Vibrant hue at baseL (clamped 0.52–0.72) | Page titles, links, general UI |
| `--accent-hover` | baseL + 0.22 (max 0.92) | Hover states |
| `--accent2` | baseL − 0.22 (min 0.40) | Nav brand |
| `--accent-dim` | `--accent` hex + `33` | 20% alpha tint |

Fallbacks: `#a855f7` / `#c084fc` / `#7e22ce`. Animation: 500ms ease-in-out sRGB interpolation via `requestAnimationFrame`. CSS `@property` + transition was scrapped — Chromium interpolates `<color>` in OKLab by default, causing washed-out midpoint flash between high-chroma complementary colors.

Art elements (`.np-art`, `.player-art-thumb`) use `background: var(--surface2)` to prevent a white flash while images load.

## Spacebar Playback

`useSpacebarPlayback()` called once from `Layout` — global toggle on every page. Pages register a first-track callback via `useRegisterFirstTrack(fn)` (module-level ref, cleared on unmount). Registered pages: AlbumPage, ArtistPage, PlaylistPage. Input suppression: no-op when focus is on INPUT / TEXTAREA / contenteditable.

## Track Share Links (AlbumPage)

URL format: `{origin}/calliope/albums/{id}?play={trackId}&note={artist}_{album}`
- `?note=` is slugified `artist_album` — human-readable, machine-ignored. Does not include track title.
- Deep link: `AlbumPage` reads `?play=` on load, scrolls the row into view (100ms timeout), attempts `playTrack()`. Browser blocks autoplay on fresh load; highlighted row shows `▶ Play` inline fallback button until track becomes active.
- `RequireAuth` encodes current `pathname + search` as `?redirect=` when bouncing to login; `LoginPage` navigates there after successful login.

## React Query Keys

| Key | Data |
|---|---|
| `['artists']` | Artist list |
| `['artist', id]` | Artist detail (albums, top tracks) |
| `['album', id]` | Album + tracks |
| `['similar', trackId]` | Similar tracks via similarity engine |
| `['playlists']` | Playlist list |
| `['playlist', id]` | Playlist detail + entries |
| `['discoveries']` | All non-dismissed discoveries |
| `['discoveries', 'artist', id]` | Scoped to one artist |
| `['search-history']` | Current user's 10 most recent visits |
| `['scanner-status']` | Polled every 2s during rescan |
| `['album-artists', albumId]` | Album-level credits — fetched eagerly on every AlbumPage load (after album data arrives); also used by AlbumCreditsSection (owner-only). React Query deduplicates both callers. |
| `['artist-singles', id]` | Singles & EPs for artist — from GET /artists/{id}/singles |
| `['me']` | Current user profile + similarity weights — staleTime: Infinity; invalidated on weight save |
| `['album-genres', albumId]` | Committed genres for an album — invalidated on POST/DELETE genre |
| `['map']` | All Music Map atlas points (GET /map) — staleTime 5min |
| `['map-lens', feature]` | Single-feature gradient values (GET /map/lens) — enabled only on the feature lens |
| `['map-pca']` | 3-PC gestalt rgb values (GET /map/pca) — enabled only on the gestalt lens |
| `['map-similar', trackId]` | Now-playing radio neighborhood for the map highlight (GET /tracks/{id}/similar) |
| `['users']` | All users `[{id, username}]` — used in PlaylistPage for permissions panel user picker and owner name display |
