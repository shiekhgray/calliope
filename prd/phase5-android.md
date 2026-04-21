# Phase 5: Android App

**Status: Not started**

## Goal

Native Android app for Calliope. Primary use cases and features:
1. Phone playback — browse library, playlists, search, stream tracks
2. Android Auto — in-car playback with voice/steering wheel controls
3. Playlist Sync — the Calliope app can download and playback playlists stored on-device

Distribution: APK sideload initially. Play Store later ($25 one-time fee).

## Developer Context

- **Experience**: First Android project — no prior Android dev or ADB experience
- **Android Studio**: Not yet installed — install latest stable before starting
- **ADB**: Will need setup walkthrough when sideloading time comes

## Tech Stack

| Concern | Library |
|---------|---------|
| UI | Jetpack Compose |
| DI | Hilt |
| HTTP | Retrofit2 + OkHttp |
| JSON | Moshi (or Gson) |
| Auth storage | EncryptedSharedPreferences |
| Playback | Media3 / ExoPlayer |
| Android Auto | MediaBrowserServiceCompat |
| Background downloads | WorkManager |
| Downloaded playlist DB | Room |
| Connectivity | ConnectivityManager (WiFi guard) |

## Screens

### Auth
- Login screen — username + password → `POST /auth/login`
- Tokens stored in `EncryptedSharedPreferences`
- Silent refresh on 401 (same pattern as web: retry with `POST /auth/refresh`)
- Logout clears tokens + Room DB

### Library Browser
- Artists list → Artist detail (top tracks + albums grid) → Album detail (tracks)
- Matches web app structure
- Pull-to-refresh on all list screens

### Search
- Single search bar → tabbed results (Artists / Albums / Tracks)

### Playlists
- List view → Playlist detail (tracks, reorder, remove, download)
- Create / delete playlists
- "Add to playlist" long-press or menu on any track

### Now Playing
- Full-screen now playing card (artwork, title, artist, album, progress scrubber)
- Previous / play-pause / next controls
- Accessible from persistent mini-player bar (bottom of screen, above nav)
- Continues to play if phone is locked

### Downloads
- Playlist download management screen
- Per-playlist download toggle
- Shows downloaded vs total tracks, storage used

## Playback Architecture

- `MusicService` extends `MediaBrowserServiceCompat`
- ExoPlayer (Media3) lives inside `MusicService` — survives screen rotation and backgrounding
- `MediaSession` exposes controls to notification, lock screen, Bluetooth headphones, Android Auto
- `PlayerController` (ViewModel-accessible) wraps `MediaController` for UI binding
- Stream URL: `GET /tracks/{id}/stream` with Bearer token in header — ExoPlayer `DefaultHttpDataSource` with auth header injected
- Play count: call `POST /tracks/{id}/played` on `onMediaItemTransitionReason == REPEAT` or natural completion (mirror web logic)

## Android Auto

- `MediaBrowserServiceCompat` provides the browsable tree:
  ```
  Root
  ├── Library
  │   └── Artists → Albums → Tracks
  ├── Playlists
  │   └── Playlist → Tracks
  └── Recently Played (top tracks across all artists, by play_count)
  ```
- Playback controls via `MediaSession` — Auto handles the UI
- Voice: "Play [artist]" via Assistant maps to the browse tree

## Offline / Downloads

- User can download any playlist for offline use
- `WorkManager` handles chunked download of each track file
- Downloaded files stored in app-private storage
- `Room` DB tracks: `playlist_id`, `track_id`, `file_path`, `downloaded_at`, status enum
- On playback: prefer local file if present, fall back to stream URL
- Downloaded playlists visible in Android Auto browse tree even offline

## WiFi Guard

- On any stream or download attempt: check `ConnectivityManager` for active network
- If cellular (not WiFi): show warning dialog — "You're on mobile data. Stream anyway?"
- Override is session-scoped (survives until app is killed, not persisted)
- Downloads: same guard, with additional note about file size

## Bluetooth / Headphone Support

- `MediaSession` handles play/pause/skip/volume from headphone controls automatically via `MediaBrowserServiceCompat`
- `AudioFocusRequest` — duck on notification, pause on phone call
- `BecomingNoisyReceiver` — pause on headphone unplug

## Build & Distribution

- **Primary test device**: Samsung Galaxy S24 Ultra (One UI 8.0 / Android 16 / API 36)
- Min SDK: API 26 (Android 8.0) — covers ~95% of active devices; S24 Ultra well above this
- Target SDK: latest stable
- Initial: generate signed APK, sideload via ADB or file transfer
- Future: Play Store (personal/family app, internal track or public listing)

### S24 Ultra Notes
- Running One UI 8.0 on Android 16 (API 36)
- No headphone jack — Bluetooth or USB-C audio; `BecomingNoisyReceiver` still needed for USB-C disconnect
- Samsung DeX support is a freebie if we use standard Compose layouts (not required, just awareness)
- Sideloading: enable Developer Options (tap Build Number 7× in Settings → About) → USB Debugging → `adb install`
- Wireless ADB available (Android 11+): Settings → Developer options → Wireless debugging — no USB cable needed for installs after initial pairing

### Android Auto
- **Car 1**: Wireless AA — phone connects over WiFi, no cable needed
- **Car 2**: Wired AA — phone connects via USB cable to head unit
- Both work transparently with `MediaBrowserServiceCompat` — AA handles the connection type, the app doesn't need to know which it is
- Test both during AA development; wired is easier to test first (more reliable connection)

## Task Breakdown

- [ ] Scaffold Kotlin project in `android/` (Gradle KTS, Hilt setup)
- [ ] Retrofit API client + auth interceptor (token attach + refresh on 401)
- [ ] Login screen + EncryptedSharedPreferences token storage
- [ ] Library browser screens (Artists → Artist → Album)
- [ ] Search screen
- [ ] Playlist screens (list, detail, create, delete, add/remove tracks)
- [ ] ExoPlayer + MusicService setup
- [ ] Now playing screen + mini-player bar
- [ ] MediaSession + notification controls
- [ ] Bluetooth / headphone / audio focus handling
- [ ] Android Auto (MediaBrowserServiceCompat browse tree)
- [ ] WorkManager playlist downloads + Room DB
- [ ] WiFi guard
- [ ] Play count reporting
- [ ] Build + sign APK, sideload and test
