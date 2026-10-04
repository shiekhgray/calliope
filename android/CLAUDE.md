# Android App — Calliope

Kotlin + Jetpack Compose, Media3/ExoPlayer, Hilt DI. Phase 5. Distribution: APK sideload.

**Builds only on Windows** — the Linux dev host has no SDK (`local.properties` points at
`C:\Users\shiek\AppData\Local\Android\Sdk`) and only JDK 8. Do not attempt `./gradlew` there;
it is not even executable. On Windows:
```
JAVA_HOME="/c/Program Files/Android/Android Studio/jbr" ./gradlew assembleDebug
```
`minSdk 26`, `targetSdk 36`, `compileSdk 36.1`. AGP 9.1.1, Kotlin 2.2.10, Compose BOM 2026.02.01.

## Structure

```
app/src/main/java/com/dresdengray/calliope/
  App.kt                      ← @HiltAndroidApp; WorkManager Configuration.Provider; download notif channel
  MainActivity.kt             ← enableEdgeToEdge(); CalliopeTheme { Surface { NavGraph } }; POST_NOTIFICATIONS request
  data/api/
    CalliopeApi.kt            ← Retrofit interface; login is @FormUrlEncoded (OAuth2), everything else JSON
    model/                    ← Auth / Library / Playlist / Search models; Moshi @JsonClass(generateAdapter)
  data/auth/
    TokenStorage.kt           ← EncryptedSharedPreferences ("calliope_tokens"); sessionActive StateFlow; generation CAS
    AuthInterceptor.kt        ← attaches Bearer; no-op when the request already has an Authorization header
    TokenAuthenticator.kt     ← OkHttp Authenticator; refreshes on 401 via the @RefreshClient api
    AuthRepository.kt         ← login / me / logout
  data/db/                    ← Room v1, single entity `downloaded_tracks` (PK: playlist_id + track_id)
  di/
    NetworkModule.kt          ← two client triples: unqualified (authenticated) + @RefreshClient (bare)
    DatabaseModule.kt
  playback/
    MusicService.kt           ← MediaLibraryService; ExoPlayer; Auto browse tree; streams via OkHttpDataSource
    PlayerViewModel.kt        ← Activity-scoped; MediaController; PlayerUiState; radioMode; WiFi guard
    MediaItems.kt             ← Track.toMediaItem() + BrowseTree node-ID scheme
    RadioQueueExtender.kt     ← /tracks/{id}/similar → MediaItems, substituting downloaded files
  ui/
    auth/LoginScreen.kt       ← insets + scroll + password reveal toggle
    navigation/NavGraph.kt    ← routes: login, main, artist/{id}, album/{id}, playlist/{id}; session watchdog
    main/                     ← MainScreen (Scaffold + bottom nav), HomeScreen
    library/ artist/ album/ search/ playlist/ player/ settings/
    common/                   ← UiState<T> (Loading/Success/Error), TrackRow, AlbumCard, Feedback, AddToPlaylistSheet
  util/
    Constants.kt              ← BASE_URL + albumArtUrl() / streamUrl()
    NetworkMonitor.kt         ← isOnWifi() for the cellular guard
  work/DownloadPlaylistWorker ← @AssistedInject; foreground dataSync; KEY_PLAYLIST_ID, TAG_PREFIX "playlist_"
```

## Auth & Session

Access tokens last **15 min**, refresh tokens **30 days** (server-side, `api/app/config.py`).

- `TokenStorage.sessionActive: StateFlow<Boolean>` is the single source of truth for "are we
  logged in". `NavGraph` collects it and navigates to `login` when it goes false, so a failed
  refresh can't leave the UI alive on a screen where every request 401s. `startDestination` is
  wrapped in `remember` so only the *initial* route comes from stored state.
- `clear()` bumps a generation counter. An in-flight refresh captures `generation` before its
  network call and publishes via `commitAccessToken(token, expectedGeneration)`, which refuses
  the write if the session was signed out meanwhile. Without this, a refresh landing after
  Sign Out resurrects a dead session.
- **Two OkHttp clients.** The unqualified one has `AuthInterceptor` + `TokenAuthenticator`;
  the `@RefreshClient`-qualified one has neither and exists solely for `POST /auth/refresh`.
  Both are `@Singleton`. Adding a third consumer of either means qualifying it correctly at
  every injection site or Hilt fails at annotation-processing time.

## Playback

`PlayerViewModel` is Activity-scoped (`by viewModels()` in `MainActivity`) so it survives
navigation, and talks to `MusicService` through a `MediaController`. Playback state is
`PlayerUiState` (currentTrack, isPlaying, positionMs, durationMs, queueTracks, currentIndex).

- Queue items carry the **plain track id** as `mediaId` — play-count reporting parses it with
  `toIntOrNull()`, and `PlayerViewModel.toTrack()` reconstructs a `Track` from it when the local
  queue is lost. The richer `BrowseTree` node IDs live only on Auto *browse* items, never on
  queue items.
- `playQueue()` substitutes a downloaded `file://` path per track when `downloadedTrackDao`
  has a DONE row and the file still exists. If every track is local, the cellular guard is skipped.
- Radio mode extension exists in **both** `PlayerViewModel` and `MusicService` — see `bugs.md`
  Bug 2, they currently double-append.

## Android Auto

`MusicService` is a `MediaLibraryService`; `automotive_app_desc.xml` declares `<uses name="media"/>`.
Browse nodes are strings parsed by `BrowseTree.parseTrack()`, which encodes both the track and the
**queue context** it was tapped in (`track/{id}/album/{albumId}`, `.../artist/{artistId}`,
`.../playlist/{playlistId}`, `.../recent`) so tapping a track can rebuild the surrounding queue.

## Non-Obvious Rules

**No `android:Theme.Material.DayNight` exists.** Platform DayNight ships only as
`android:Theme.DeviceDefault.DayNight`, added in **API 29** — it compiles against compileSdk and
then fails to inflate on API 26–28. `Theme.Material3.DayNight` needs a `com.google.android.material`
dependency. Use `values/` + `values-night/` with `Theme.Material.Light.NoActionBar` /
`Theme.Material.NoActionBar` (`Theme.Material` *is* the dark one).

**The window background and the Compose color scheme are independent.** `CalliopeTheme` keys off
`isSystemInDarkTheme()` + dynamic color, but the window background comes from `themes.xml`. If they
disagree you get invisible content — near-white `onSurface` text on a white window. `MainActivity`
wraps everything in a `Surface(colorScheme.background)` to make this structurally impossible; don't
remove it. Screens with a `Scaffold` are incidentally safe, bare-`Column` screens are not.

**`enableEdgeToEdge()` + targetSdk 36 means the IME never resizes the window.** Any centered or
non-scrollable screen needs `.imePadding()` and `.verticalScroll()`, or the keyboard simply covers
the bottom of it with no way to reach it. Put inset modifiers *outside* `verticalScroll` so the
keyboard shrinks the scrollable viewport rather than the content; keep `fillMaxSize()` outside the
scroll modifier so a full-height `minHeight` survives and `Arrangement.Center` still centers.

**OkHttp application interceptors do NOT re-run on authenticator retries.** `RetryAndFollowUpInterceptor`
sits below the `addInterceptor` chain and the authenticator's retry loop lives inside it. Only
`addNetworkInterceptor` interceptors see retries. Don't reason about `AuthInterceptor` as if it runs
per attempt.

**Never refresh a token through the client the Authenticator is attached to.** OkHttp runs
`authenticate()` on the thread of the 401'd call *while that call still holds one of its 5
per-host slots* (`maxRequestsPerHost` default). Five simultaneous 401s then leave no slot for any
refresh, and because queued calls never start, their timeouts never begin counting — the client
deadlocks permanently. This is what `@RefreshClient` is for.

**`POST /auth/login` returns 401 with `WWW-Authenticate: Bearer`,** so a mistyped password would
otherwise invoke the Authenticator and could clear a live session. `authenticate()` returns null
early for paths ending in `/auth/login` or `/auth/refresh`.

**`HttpLoggingInterceptor` at `Level.BODY` buffers the entire response body** (`source.request(Long.MAX_VALUE)`).
Audio now streams through the same authenticated client, so the logger must exempt `/stream` or
playback stalls and memory balloons. Logging is debug-only.

**Streaming shares the authenticated client,** so a playing track holds a host slot for its whole
duration, leaving fewer for API calls. If API calls start queueing during playback, raise
`maxRequestsPerHost` or give streaming its own client. Coil uses its own default client, so album
art does not contend.

**AGP no longer generates `BuildConfig` by default** — `buildConfig = true` in `buildFeatures` is
required for `BuildConfig.DEBUG`.

**The `MasterKey` behind `EncryptedSharedPreferences` is non-exportable Keystore material.** A
backed-up-and-restored prefs file cannot be decrypted and throws on access, so `calliope_tokens.xml`
is excluded in both `backup_rules.xml` and `data_extraction_rules.xml`. Any new encrypted prefs file
needs the same treatment.

**`network_security_config.xml`'s `<base-config>` applies to release builds too** — despite the
comment in the file claiming otherwise. It currently permits cleartext traffic and trusts
user-installed CAs in release, which is weaker than Android's default for targetSdk 24+. Only
`<debug-overrides>` is debug-scoped.

**Login is form-encoded, not JSON** — `@FormUrlEncoded` + `@Field`, matching FastAPI's
`OAuth2PasswordRequestForm`. Every other endpoint is JSON.

## Known Issues

See `bugs.md` at the repo root for the active list. Android Auto radio toggle (Bug 1) and
duplicate radio queue extension (Bug 2) are open.
