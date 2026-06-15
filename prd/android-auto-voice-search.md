# Android Auto — Voice Search

**Status: Not started**

## Goal

Let the user control Calliope hands-free in the car. Saying *"Play **[artist / album / song]** on Calliope"* (or using Assistant / the Auto search button) should resolve the spoken query against the existing Calliope search API, build a playable queue, and start playback — without the user touching the screen.

This is the first of the two items deferred in [android-auto.md](android-auto.md) ("In-car search" and "Voice 'Play [artist]'"). Both are covered here because voice routing and the search UI share the same query-resolution code.

## Why

The browse tree (artists → albums → playlists → recently played) is built and works, but every interaction requires looking at and tapping the head unit. Voice is the safest and most natural in-car input. The backend search endpoint (`GET /search?q=`) already exists and powers the phone Search screen, so the work is almost entirely on the Android side — wiring Media3's voice/search callbacks to the existing API.

## What's Already Built

- `MusicService` extends `MediaLibraryService` with a fully implemented `libraryCallback` (browse tree, queue building, radio mode). See [android-auto.md](android-auto.md).
- `CalliopeApi.search(q: String): SearchResults` — returns `{ artists, albums, tracks }`. Used by the phone `SearchScreen` / `SearchViewModel`.
- Queue-building helpers in `MusicService`: `buildQueueForContext(ctx)`, `albumTracks(albumId)`, and `RadioQueueExtender.toMediaItem(track)` (handles offline file substitution + stream auth).
- `BrowseTree` node-ID scheme for encoding queue context into media IDs.

None of the search/voice callbacks are implemented yet — `grep` for `searchQuery`, `onSearch`, `onGetSearchResult`, `PlayFromSearch` returns nothing.

## How Voice Reaches the App (Media3)

There are two entry points, and we want both:

1. **Voice "Play X" (no screen)** — Assistant / "Hey Google, play X on Calliope" routes to the session as a call to `onSetMediaItems` (and/or `onAddMediaItems`) where the supplied `MediaItem` carries **`requestMetadata.searchQuery`** instead of a resolvable `mediaId`/URI. The current `onSetMediaItems` only calls `BrowseTree.parseTrack(mediaId)` and ignores `searchQuery`, so today these requests no-op. This is the highest-value piece.

2. **In-car search UI** — the search affordance on the Auto Now Playing / browse surface calls `MediaLibrarySession.Callback.onSearch` (notify results available) and `onGetSearchResult` (return the paged result list as browsable/playable `MediaItem`s). Tapping a result then flows through the existing `onSetMediaItems` path by `mediaId`.

## Behaviour

### Query → queue resolution

A spoken/typed query resolves to a queue using this precedence:

| Match | Resulting queue | Start |
|-------|-----------------|-------|
| Exact-ish **track** title hit | That track + radio extension on (treat as a seed) | the track |
| **Album** title hit | All tracks in the album | track 0 |
| **Artist** name hit | The artist's Top Tracks (`getArtistTopTracks`) | track 0 |
| Multiple/ambiguous | First non-empty section in order: tracks → albums → artists; for the search-UI path, return all sections as a browsable result list | — |
| No results | Return empty result / `RESULT_ERROR_BAD_VALUE`; do not change current playback | — |

Resolution helper (new): `suspend fun resolveSearchQuery(query: String): Pair<List<Track>, Int>?` living in `MusicService` (or a small `SearchResolver` if it grows). It calls `api.search(query)`, applies the precedence above, and reuses `albumTracks` / `getArtistTopTracks` / `buildQueueForContext` to materialise the queue.

### Voice playback path (`onSetMediaItems`)

In `onSetMediaItems`, before the existing `BrowseTree.parseTrack` branch:

```kotlin
val voiceQuery = mediaItems.firstOrNull()?.requestMetadata?.searchQuery
if (!voiceQuery.isNullOrBlank()) {
    val resolved = resolveSearchQuery(voiceQuery)
        ?: return@future MediaSession.MediaItemsWithStartPosition(emptyList(), 0, 0L)
    val (tracks, idx) = resolved
    val items = tracks.map { radioExtender.toMediaItem(it) }
    autoInitiatedPlayback = true          // enable Auto radio extension
    radioPlayedIds.clear()
    radioPlayedIds.addAll(tracks.map { it.id })
    return@future MediaSession.MediaItemsWithStartPosition(items, idx, 0L)
}
```

A single-track voice result sets `autoInitiatedPlayback = true` so radio mode keeps the music going after the one song — matching the in-car "never stop" goal.

### Search UI path (`onSearch` / `onGetSearchResult`)

- `onSearch(session, browser, query, params)` → run `api.search(query)`, cache the `SearchResults` keyed by query string, call `session.notifySearchResultChanged(browser, query, itemCount, params)`.
- `onGetSearchResult(session, browser, query, page, pageSize, params)` → return the cached results as `MediaItem`s: tracks as playable items (mediaId in `track/{id}/...` form so the existing queue builder fires on tap), artists/albums as browsable folders reusing `browseFolder(...)`.

## API Changes

**None.** `GET /search?q=` already returns artists, albums, and tracks in the shape the Android `SearchResults` model expects. `getArtistTopTracks`, `getAlbum`, and `getPlaylist` are all already wired.

> Note: `GET /search` matches across artists/albums/tracks server-side; we rely on it rather than re-implementing fuzzy matching on-device. If voice match quality proves weak (e.g. partial artist names), a follow-up could add a `type=` filter or relevance scoring to the endpoint — out of scope here.

## Manifest / Discoverability

- `automotive_app_desc.xml` already declares `<uses name="media"/>` — sufficient; no `SEARCH_SUPPORTED` browser-service extra is needed for the Media3 `onSearch` path.
- Verify Assistant routing works without an explicit `MEDIA_PLAY_FROM_SEARCH` intent filter (Media3 surfaces the query via `requestMetadata.searchQuery` on the session). Only add a legacy intent filter if device testing shows Assistant fails to reach the session.

## Implementation Notes

- **Reuse, don't fork**: `resolveSearchQuery` must build queues through the same helpers the browse tree uses (`albumTracks`, `getArtistTopTracks`, `radioExtender.toMediaItem`) so offline-file substitution and stream auth stay consistent.
- **mediaId for resolved tracks**: resolved playable queue items use the plain track id as `mediaId` (same convention as the browse path) so play-count reporting (`onMediaItemTransition`) and radio seeding keep working unchanged.
- **Threading**: all callbacks bridge suspend API calls via `serviceScope.future { ... }`, as elsewhere in `MusicService`.
- **Result cache for `onGetSearchResult`**: keep a tiny `query -> SearchResults` map (last 1–2 queries) so `onSearch` and the paged `onGetSearchResult` don't double-hit the API.

## Out of Scope (This Pass)

- Voice commands beyond "play" (e.g. "add to playlist", "shuffle my library") — Auto/voice grammar is limited; revisit if needed.
- Server-side search relevance tuning / `type=` filter — only if device testing shows poor matches.
- Spoken feedback / TTS confirmations — rely on Auto's default UI.

## Task Breakdown

- [ ] Add `resolveSearchQuery(query): Pair<List<Track>, Int>?` to `MusicService` (precedence: track → album → artist)
- [ ] Handle `requestMetadata.searchQuery` in `onSetMediaItems` (and `onAddMediaItems`) for voice "Play X"
- [ ] Implement `onSearch` + `onGetSearchResult` for the in-car search UI (with small result cache)
- [ ] Map `SearchResults` → `MediaItem`s (tracks playable via `track/{id}/...` IDs; artists/albums browsable via `browseFolder`)
- [ ] Single-track voice result sets `autoInitiatedPlayback = true` so radio continues
- [ ] Verify Assistant routing reaches the session; add legacy intent filter only if required
- [ ] Test: "Hey Google, play [artist] on Calliope" → artist top tracks play, radio extends
- [ ] Test: "...play [album]..." → full album queued; "...play [song]..." → song + radio
- [ ] Test: in-car search button → results render → tap plays correct context queue
- [ ] Test on both cars (wired + wireless)
- [ ] Update [android-auto.md](android-auto.md) "Out of Scope" note and `.todo`
