# Android Auto

**Status: Implemented — pending on-device build/test (Windows toolchain + both cars)**

## Goal

Full Android Auto integration for Calliope — browse the music library, play albums and playlists, and continue listening indefinitely via radio mode. Optimised for in-car use: minimal taps, seamless queue continuation, no interaction required once playback starts.

## Hardware Context

- **Car 1**: Wireless Android Auto (phone connects over WiFi)
- **Car 2**: Wired Android Auto (phone connects via USB)
- Both work transparently via `MediaLibraryService` — the app does not need to distinguish them

## What's Already Built

`MusicService` already extends `MediaLibraryService` (Media3) and holds a `MediaLibrarySession` with a stub `libraryCallback` that returns the root node and empty children. The foundation is in place; this PRD covers filling it out.

## Browse Tree

```
Root
├── Artists
│   └── Artist
│       ├── ▶ Top Tracks          ← virtual folder; tracks sorted by play_count desc
│       └── Album 1
│           └── Tracks
│           ...
├── Playlists
│   └── Playlist
│       └── Tracks
└── Recently Played               ← flat list of tracks sorted by play_count desc, limit 50
```

### Node ID scheme

| Node | ID |
|------|----|
| Root | `root` |
| Artists folder | `artists` |
| Artist | `artist/{id}` |
| Top Tracks folder | `artist/{id}/top-tracks` |
| Album | `album/{id}` |
| Track (in album context) | `track/{id}/album/{albumId}` |
| Track (in top-tracks context) | `track/{id}/artist/{artistId}` |
| Playlists folder | `playlists` |
| Playlist | `playlist/{id}` |
| Track (in playlist context) | `track/{id}/playlist/{playlistId}` |
| Recently Played folder | `recently-played` |
| Track (in recently-played) | `track/{id}/recent` |

Context is encoded in the track node ID so `onGetChildren` on a track's parent always knows which queue to build.

### Top Tracks

- Tracks belonging to this artist (via `album_artists` or `albums.artist_id`), sorted by `play_count` desc
- Limit: 25 tracks
- API call: `GET /artists/{id}/tracks?sort=play_count&limit=25` — add this endpoint if it doesn't exist

### Recently Played

- All tracks, sorted by `play_count` desc, limit 50
- Serves as a "greatest hits across the whole library" list for quick car listening
- API call: `GET /tracks?sort=play_count&limit=50`

## Playback Behaviour

### Queue building

When the user taps any track in Auto, the full context is enqueued — not just the single track:

| Context | Queue |
|---------|-------|
| Album | All tracks in the album, starting from the tapped track |
| Top Tracks | All top tracks for that artist, starting from the tapped track |
| Playlist | All tracks in the playlist, starting from the tapped track |
| Recently Played | All 50 recently played tracks, starting from the tapped track |

`onPlayFromMediaId` / `onAddQueueItem` should receive the tapped track's node ID, extract the context, fetch siblings from the API, build `MediaItem` list, hand to ExoPlayer via `player.setMediaItems(items, startIndex, 0)`.

### Radio mode

- When the queue runs out, fetch similar tracks via `GET /tracks/{id}/similar?limit=10`, filter out track IDs already played this session, append up to 5 to the ExoPlayer queue
- "Already played" is an in-memory set on `MusicService`, cleared on new manual play or app kill
- Radio mode is **on by default**; user can toggle it via a custom action button on the Auto Now Playing screen (see below)
- Implementation mirrors `checkAndExtendRadioQueue` in `PlayerViewModel` — extract shared logic into a `RadioQueueExtender` helper injectable into both

### Custom action: Radio toggle

Media3 `CommandButton` added to the session's `customLayout`:

```
Icon:  Icons.Filled.Radio  (on)  /  Icons.Outlined.Radio  (off)
Label: "Radio: On" / "Radio: Off"
```

Auto displays custom layout buttons on the Now Playing card. Tapping toggles `radioModeEnabled` state in `MusicService` and updates the session's custom layout so the icon reflects current state. Default: **on**.

## API Changes

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /artists/{id}/top-tracks` | **exists** | Used for Top Tracks folder. Limit hardcoded to 10 — bump to 25 for Auto. Also uses `albums.artist_id` filter rather than the `album_artists` join, so tracks on albums where the artist is credited via `album_artists` (but isn't the display `artist_id`) are missed. Fix the join to match `GET /artists/{id}/albums` when implementing Auto. |
| `GET /tracks?sort=play_count&limit=N` | **needs adding** | Used for Recently Played folder. Returns standard track shape (id, title, album_id, album_title, artist_id, artist_name, play_count, duration_ms, format). |
| `GET /tracks/{id}/similar` | **exists** | Used for radio queue extension. No changes needed. |

## Implementation Notes

### Coroutine / Futures bridge

`onGetChildren` and `onGetItem` must return `ListenableFuture`. Use `serviceScope.future { ... }` (kotlinx-coroutines-guava) to call suspend API functions and bridge to `Futures`:

```kotlin
override fun onGetChildren(...): ListenableFuture<LibraryResult<ImmutableList<MediaItem>>> =
    serviceScope.future {
        val items = api.getAlbumTracks(albumId).map { it.toMediaItem() }
        LibraryResult.ofItemList(items, null)
    }
```

Add `kotlinx-coroutines-guava` to `libs.versions.toml` if not present.

### MediaItem construction

Playable track items need:
- `mediaId` = node ID string
- `requestMetadata.mediaUri` = stream URI (`https://dresdengray.com/calliope/api/tracks/{id}/stream`)
- `MediaMetadata`: title, artist, album title, album art URI (`/calliope/api/albums/{albumId}/art`), `isPlayable = true`, `isBrowsable = false`

Browsable folder items need `isPlayable = false`, `isBrowsable = true`, no URI.

### Auth on streams

ExoPlayer's `DefaultHttpDataSource.Factory` already injects the Bearer token via `AuthInterceptor` on `OkHttpClient`. No additional work needed for Auto streams.

### Offline / downloaded tracks

When building `MediaItem` for a track, check `DownloadedTrackDao.findDoneByTrackId(trackId)` — if a local file exists, use `Uri.fromFile(localPath)` instead of the stream URI. Same logic already exists in `PlayerViewModel.playQueue`.

## Out of Scope (This Pass)

- **In-car search** — `onSearch` callback left unimplemented; defer to a future PRD
- **Voice "Play [artist]"** — depends on search; defer with search
- **Add to playlist** — not feasible within Auto's UI constraints; phone-only feature

## Task Breakdown

- [x] Add `kotlinx-coroutines-guava` dependency
- [x] Add `GET /tracks?sort=play_count&limit=N` endpoint (Recently Played) — already present
- [x] Fix `GET /artists/{id}/top-tracks` — limit defaults to 25, uses `album_artists` join — already present
- [x] Implement `onGetChildren` for all node types in `MusicService.libraryCallback`
- [x] Implement `onGetItem` (needed for Auto to resolve individual track metadata)
- [x] Queue building — implemented via `onSetMediaItems` (Media3 idiom; replaces deprecated `onPlayFromMediaId`) + `onAddMediaItems` resolution; loads siblings, returns `MediaItemsWithStartPosition`
- [x] Extract `RadioQueueExtender` from `PlayerViewModel`; inject into `MusicService`
- [x] Radio toggle `CommandButton` in session `customLayout`; wire state in `MusicService`
- [x] Offline track URI substitution in Auto queue builder (`RadioQueueExtender.toMediaItem` / shared `Track.toMediaItem`)
- [ ] End-to-end test: browse Artists → Artist → Top Tracks → play; verify queue and radio extension
- [ ] End-to-end test: browse Playlists → Playlist → play; verify downloaded tracks play from local file
- [ ] Test on both cars (wired + wireless)

## Implementation Notes (as built)

- **Queue building** uses Media3's `onSetMediaItems` rather than the legacy `onPlayFromMediaId`. When an external controller (Auto) taps a browse item, the tapped node ID is parsed (`BrowseTree.parseTrack`), the full context is fetched from the API, and the resolved playable queue + start index is returned as `MediaItemsWithStartPosition`. `onAddMediaItems` is also overridden to resolve mediaId-only items.
- **Phone vs Auto disambiguation**: `controller.packageName == packageName` identifies our own phone UI, whose items already carry URIs and are played as-is. Service-side radio auto-extension is gated on `autoInitiatedPlayback`, set true only when playback originates from the Auto browse tree — so the phone's radio (default OFF, toggled in NowPlaying) and Auto's radio (default ON, toggled via custom action) never double-extend the shared ExoPlayer queue.
- **Browse vs playback mediaIds**: browse items carry node IDs (e.g. `track/5/album/3`); the resolved queue items carry the plain track id as mediaId so existing play-count reporting and `PlayerViewModel.toTrack()` reconstruction keep working unchanged.
- **Radio icons**: `res/drawable/ic_radio_on.xml` (filled) / `ic_radio_off.xml` (outline) back the `CommandButton`.
- **API was already complete**: all three endpoints existed before this pass; only the Android side was implemented.
