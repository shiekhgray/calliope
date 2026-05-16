# PRD: Android Home Screen Redesign

## Overview

Replace the current 3-tab layout (Library / Search / Playlists) with a smarter Home tab that doubles as the Now Playing screen. When nothing is playing the Home tab shows the artist library. When something is playing it shows full now-playing content. The Library tab is removed entirely. Add a Stop button to the transport controls. Add a persistent gear icon to the Home top bar that opens a settings sheet (Change Password, Sound Matching, Sign Out).

---

## Navigation Structure

### Before
```
Bottom nav: Library | Search | Playlists
Separate route: now-playing (pushed onto back stack from mini-player tap)
```

### After
```
Bottom nav: Home | Search | Playlists
No separate now-playing route — content lives inside the Home tab
```

The `now-playing` route and `NowPlayingScreen` composable are removed. The `MainScreen` Home tab renders either `LibraryContent` or `HomeNowPlayingContent` depending on whether `currentTrack != null`.

---

## Home Tab — Two States

### State A: Nothing Playing (`currentTrack == null`)

- **Top bar**: title "Calliope", gear icon (⚙) in actions slot
- **Content**: full artist list (current `LibraryScreen` content, minus its own scaffold — raw `LazyColumn`)
- Tapping an artist navigates to `artist/{id}` as before

### State B: Something Playing (`currentTrack != null`)

- **Top bar**: title "Now Playing", gear icon (⚙) in actions slot
- **Content**: scrollable `LazyColumn` with sections (see below)
- Mini-player bar is **not** shown on the Home tab when in State B (it would be redundant — the full controls are already visible). It continues to show on Search and Playlists tabs.

---

## Home Tab — Now Playing Content (State B)

Sections rendered top-to-bottom in a single `LazyColumn`:

### 1. Album Art
- `AsyncImage`, 300×300dp, `RoundedCornerShape(12.dp)`, centered, `ContentScale.Crop`
- Same URL pattern as current: `Constants.albumArtUrl(track.albumId)`

### 2. Track Info
- Title: `titleLarge`, centered, max 2 lines
- Artist: `bodyLarge`, `onSurfaceVariant`, centered, max 1 line, tappable → `artist/{id}`
- Album: `bodySmall`, `onSurfaceVariant`, centered, max 1 line, tappable → `album/{id}`

### 3. Scrubber
- `Slider` with `onValueChange` / `onValueChangeFinished` (scrub-and-release pattern, same as current)
- Time labels: elapsed left, total right, `bodySmall`, `onSurfaceVariant`

### 4. Transport Controls
Single `Row`, `SpaceEvenly`, five buttons:

| Position | Icon | Action |
|---|---|---|
| 1 | `SkipPrevious` (40dp) | `skipToPrev()` |
| 2 | `Pause` / `PlayArrow` (56dp, primary tint) | `togglePlayPause()` |
| 3 | `Stop` (40dp, `onSurfaceVariant` tint) | `stopPlayback()` — see below |
| 4 | `SkipNext` (40dp) | `skipToNext()` |

Stop is visually secondary (smaller, dimmer tint) so it doesn't compete with play/pause.

### 5. Radio Mode
- `FilterChip` with Radio icon — same as current

### 6. Previously Played
- Section header: "Previously Played", `titleSmall`, `onSurfaceVariant`
- Source: tracks at queue positions `0 ..< queueIndex` (earlier in the current queue), shown in **reverse** order (most recent first), max 10
- Each row: `TrackRow` (tap plays that queue position via `seekToQueueItem(index)`)
- Hidden if empty (nothing played yet in this session / queue at position 0)

### 7. Upcoming
- Section header: "Up Next", `titleSmall`, `onSurfaceVariant`
- Source: tracks at queue positions `queueIndex+1 .. end`
- Each row: `TrackRow` (tap seeks to that queue position)
- Hidden if empty

### 8. Similar Tracks
- Section header: "Similar Tracks", `titleSmall`, `onSurfaceVariant`
- Source: `playerViewModel.similarTracks` (existing flow — fetched whenever `currentTrack` changes)
- Each row: `TrackRow` (tap calls `playerViewModel.playQueue(listOf(track))`)
- Hidden if empty or still loading

---

## Stop Button Behavior

`PlayerViewModel.stopPlayback()`:
1. Calls `player.stop()` on the Media3 `ExoPlayer`
2. Clears the Media3 `MediaItem` list (`player.clearMediaItems()`)
3. Sets `currentTrack = null`, `queue = emptyList()`, `queueIndex = 0`
4. Does **not** clear `similarTracks` (irrelevant once track is null)
5. Emits new `uiState` — Home tab sees `currentTrack == null`, switches to State A (Library)

No navigation call needed — the tab content recomposes automatically.

---

## Mini-Player Bar

No changes to `MiniPlayerBar.kt`. It continues to show on Search and Playlists tabs (wherever `currentTrack != null`). The tap-to-open-now-playing gesture currently navigates to `now-playing` route — this is rerouted to switch the bottom nav selection to the Home tab (index 0) instead of pushing a route.

`MainScreen` passes `onOpenNowPlaying = { selectedTab = 0 }` to `MiniPlayerBar`.

---

## Settings Sheet

Triggered by the gear icon (⚙) in the Home top bar. Opens a `ModalBottomSheet`.

### Items

#### 1. Change Password
- Tapping opens a second `AlertDialog` (or nested bottom sheet) with three fields: Current Password, New Password, Confirm New Password
- On submit: `POST /auth/change-password` `{ current_password, new_password }`
- Success: dismiss dialog, show `Snackbar("Password updated")`
- Error: show inline error text below the field

#### 2. Sound Matching
- Tapping dismisses the settings sheet and opens a dedicated full-screen or bottom sheet for the sliders
- **9 sliders** across 3 groups, matching the web `SimilarityWeightsModal` exactly:

| Group | Sliders |
|---|---|
| Rhythm | Tempo, Beat Strength, Rhythm Regularity |
| Timbre | Brightness, Roughness, Warmth |
| Harmony | Key/Mode, Chord Complexity, Tonal Stability |

- Each slider: range 1–10, integer steps, label + current value shown
- On save: `PUT /auth/similarity-weights` with all 9 values
- Weights loaded on sheet open via `GET /auth/me` (already cached in `PlayerViewModel` or fetched fresh)
- Success: dismiss, show `Snackbar("Sound matching saved")`

#### 3. Sign Out
- Single `TextButton` styled in `error` color
- On tap: show `AlertDialog("Sign out?", "You'll need to log in again.")` with Cancel / Sign Out
- On confirm: `tokenStorage.clear()` + navigate to `login`, clearing back stack

---

## NavGraph Changes

- Remove `composable("now-playing")` route
- Remove `onOpenNowPlaying` parameter from `MainScreen`, `AlbumScreen`, `ArtistScreen`, `PlaylistDetailScreen`, `NowPlayingScreen`
- Replace with `onOpenHomeTab: () -> Unit` callback that sets `selectedTab = 0` in `MainScreen` (passed down via `MainScreen` to children as needed, or handled via shared state)
- `NowPlayingScreen.kt` file is deleted (content merged into Home tab)

---

## Files Touched

| File | Change |
|---|---|
| `ui/main/MainScreen.kt` | Add tab state, route Home tab to new `HomeScreen` composable |
| `ui/main/HomeScreen.kt` | **New** — wraps `LibraryContent` (State A) or `NowPlayingContent` (State B) |
| `ui/player/NowPlayingScreen.kt` | **Deleted** — content moved to `HomeScreen` |
| `ui/library/LibraryScreen.kt` | Extract inner list to `LibraryContent()` (no scaffold), keep `LibraryScreen` as scaffold wrapper for direct use if needed |
| `playback/PlayerViewModel.kt` | Add `stopPlayback()` |
| `ui/navigation/NavGraph.kt` | Remove `now-playing` route; update `onOpenNowPlaying` → `onOpenHomeTab` |
| `ui/settings/SettingsSheet.kt` | **New** — `ModalBottomSheet` with the three items |
| `ui/settings/ChangePasswordDialog.kt` | **New** |
| `ui/settings/SoundMatchingSheet.kt` | **New** — 9-slider UI |
| `data/api/CalliopeApi.kt` | Add `changePassword()` endpoint if not present |

---

## API Dependencies

| Endpoint | Already exists? | Notes |
|---|---|---|
| `PUT /auth/similarity-weights` | Yes | Used by web Sound Matching |
| `GET /auth/me` | Yes | Returns weights + username |
| `POST /auth/change-password` | Verify | Web has `ChangePasswordModal` — check API router |

---

## Out of Scope

- Rescan library (omitted per user request)
- Import music (omitted per user request)
- WiFi-only playback toggle (existing `NetworkMonitor` / warning dialog is unchanged)
- Android Auto (separate PRD)
