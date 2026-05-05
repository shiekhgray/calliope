# PRD: Playlist Similar Tracks

## Goal

Surface 10 suggested tracks at the bottom of every playlist page, derived from
the sonic character of the playlist's recent tracks. Helps users discover what
fits and quickly extend their playlists.

---

## User-Facing Behavior

### "Similar Tracks" section

Appears at the bottom of `PlaylistPage`, below the track list, for all viewers
(owner and non-owners alike). Heading: **"Similar Tracks"**.

- **Empty playlist**: section is hidden entirely (no heading, no empty state).
- **No vectors yet**: if none of the seed tracks have been indexed, section is
  hidden. If some are indexed and some aren't, proceed with what's available.
- **Normal case**: 10 tracks displayed, each with a play button, title, artist,
  album name, and an **"Add"** button to append the track to the playlist.

### Seeding

- **Seed pool**: the last 10 tracks in the playlist by position. If the playlist
  has fewer than 10 tracks, use all of them.
- **Duplicate seeds**: if the same track appears multiple times in the seed pool
  (e.g. the same song is at positions 7 and 9), it counts as multiple seed
  vectors — it pulls the centroid further toward its sound.

### Results

- **Deduplication**: any track already present in the playlist (at any position,
  any number of times) is excluded from results.
- **Limit**: 10 results.
- **Ordering**: descending cosine similarity to the centroid.

### Live updates

The section refetches whenever tracks are added or removed from the playlist.
No manual refresh needed.

### Actions on each suggested track

| Action | Behavior |
|---|---|
| Play button | Immediately plays the track (replaces current queue position, track enrichment included) |
| **Add** button | Appends the track to the end of the playlist; track disappears from the suggestions list |

---

## Algorithm

1. **Select seed tracks**: last N playlist positions (N = min(10, playlist length)).
   Preserve duplicates — a track at two positions yields two vector entries.
2. **Fetch vectors**: `SELECT track_id, feature_vector FROM track_vectors WHERE
   track_id = ANY(:seed_ids)`. Tracks with no vector are silently skipped.
3. **Apply user weights**: apply the logged-in user's `sim_weight_*` columns as
   per-dimension multipliers (same logic as `GET /tracks/{id}/similar`).
4. **Compute centroid**: average all weighted vectors, including duplicate
   contributions. One track appearing twice in the seed pool counts twice in the
   average.
5. **L2-normalize** the centroid.
6. **pgvector query**: find the top `limit + playlist_length` tracks by cosine
   similarity to the centroid, then filter out any `track_id` already in the
   playlist. Take the top `limit` survivors.

If fewer than 2 seed tracks have vectors, return an empty list (no meaningful
centroid from a single data point is still acceptable, but the section should
show only when there's genuine signal).

---

## API Changes

### `GET /playlists/{id}/similar?limit=10`

Auth required. Uses the logged-in user's similarity weights.

**Response** — same shape as `GET /tracks/{id}/similar`:

```json
[
  {
    "id": 441,
    "title": "Track Title",
    "duration_ms": 214000,
    "track_number": 3,
    "album_id": 88,
    "album_title": "Album Name",
    "artist_id": 12,
    "artist_name": "Artist Name",
    "file_path": "Artist/Album/03 Track.mp3",
    "format": "mp3",
    "play_count": 7
  }
]
```

**Error cases**:
- `404` — playlist not found
- `200 []` — playlist empty, no vectors available, or fewer than 2 seeds indexed

The endpoint is intentionally permissive: non-owners can call it (the playlist
visibility model doesn't gate reading playlist contents today).

---

## Web UI Changes

### `PlaylistPage.jsx` — new "Similar Tracks" section

Below the existing track list (and below any "Add tracks" controls):

```
Similar Tracks
─────────────────────────────────────────────────────
▶  Track Title          Artist Name · Album Name   [Add]
▶  Track Title          Artist Name · Album Name   [Add]
   …
```

**React Query key**: `['playlist-similar', playlistId]`. The query is
**disabled** when the playlist has 0 tracks.

**Dependency on playlist mutations**: after any add-track or remove-track
mutation succeeds, invalidate both `['playlist', playlistId]` and
`['playlist-similar', playlistId]` — so suggestions update to reflect the new
playlist state without a page reload.

**Play button**: calls `playTrack()` with full enrichment
(`album_id`, `album_title`, `artist_id`, `artist_name`) — same as tracks
anywhere else in the app.

**Add button**: calls `POST /playlists/{id}/tracks` with the suggested
`track_id`. On success, invalidates `['playlist', playlistId]` and
`['playlist-similar', playlistId]`. The track disappears from suggestions
immediately when the invalidation resolves (no optimistic removal needed —
the refetch is fast).

**Loading state**: skeleton rows (same count as the result limit) while the
query is in flight. No spinner header.

**Empty / hidden**: if the API returns `[]`, render nothing — no heading,
no empty-state message.

---

## Out of Scope

- Showing a "why" explanation for each suggestion
- Seeding from arbitrary track selections (not just playlist tail)
- Configuring the seed window size (hardcoded 10)
- Android playlist page (Android similar tracks are on NowPlayingScreen; no
  playlist-level suggestions planned at this time)
- Saving the suggestions as a new playlist
