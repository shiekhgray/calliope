# Android Auto

**Status: Not started**

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

Two new endpoints needed (or verify they already exist):

| Endpoint | Used for |
|----------|----------|
| `GET /artists/{id}/tracks?sort=play_count&limit=N` | Top Tracks folder |
| `GET /tracks?sort=play_count&limit=N` | Recently Played folder |

Both return the standard track shape already used elsewhere. The similarity endpoint (`GET /tracks/{id}/similar`) already exists.

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

- [ ] Add `kotlinx-coroutines-guava` dependency
- [ ] Add API endpoints: `GET /artists/{id}/tracks` and `GET /tracks?sort=play_count`
- [ ] Implement `onGetChildren` for all node types in `MusicService.libraryCallback`
- [ ] Implement `onGetItem` (needed for Auto to resolve individual track metadata)
- [ ] Queue building on `onPlayFromMediaId` — load siblings, call `player.setMediaItems`
- [ ] Extract `RadioQueueExtender` from `PlayerViewModel`; inject into `MusicService`
- [ ] Radio toggle `CommandButton` in session `customLayout`; wire state in `MusicService`
- [ ] Offline track URI substitution in Auto queue builder
- [ ] End-to-end test: browse Artists → Artist → Top Tracks → play; verify queue and radio extension
- [ ] End-to-end test: browse Playlists → Playlist → play; verify downloaded tracks play from local file
- [ ] Test on both cars (wired + wireless)
