# Releases Discovery Page

A "Releases" page that surfaces albums from artists already in your library that you don't own yet, powered by the iTunes Search API.

## Goal

Given ~246 artists in the Calliope library, periodically query iTunes for each artist's full discography and show albums not yet in the local library. Lets you discover new or missed releases from artists you already know you like.

## Data Source

**iTunes Search API** — free, no auth, no API key required.

Query per artist: `https://itunes.apple.com/search?term={artist}&entity=album&limit=50`

Returns: `collectionName` (album title), `releaseDate`, `artworkUrl100`, `collectionId`, `artistName`.

## Database

New `discoveries` table:

```
discoveries    id, artist_id (FK), itunes_collection_id, album_title, release_date, artwork_url, dismissed
```

- `itunes_collection_id` is unique — safe to upsert on refresh
- `dismissed` defaults false; set true when user clicks dismiss
- No separate "acquired" flag needed — if an album appears in the `albums` table after a rescan, it's filtered out at query time

## API Endpoints

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| `POST` | `/discover/refresh` | required | Kicks off background task; 409 if already running |
| `GET` | `/discover/status` | no | `{running: bool, last_refreshed: datetime \| null}` |
| `GET` | `/discover` | no | Returns non-dismissed discoveries not in library |
| `POST` | `/discover/{id}/dismiss` | required | Marks dismissed=true |

### Refresh task behavior
- Walks all artists in DB
- Queries iTunes for each (modest rate, ~246 requests)
- Upserts into `discoveries` by `itunes_collection_id`
- Does NOT un-dismiss previously dismissed entries
- Runtime: ~30–60 seconds

### GET /discover response shape
```json
[
  {
    "id": 1,
    "artist_id": 42,
    "artist_name": "Ninajirachi",
    "album_title": "Fairy Floss",
    "release_date": "2022-03-01",
    "artwork_url": "https://..."
  }
]
```

Filtering logic:
- `dismissed = false`
- No album with matching title exists for that artist in `albums` table (case-insensitive)

## Web UI

New **Releases** page (`/releases`):

- Refresh button at top — triggers `POST /discover/refresh`, then polls `/discover/status` every 2s (same pattern as Rescan Library)
- Shows last-refreshed timestamp
- Album cards: artwork (from iTunes URL), title, artist name, year
- Per-card **Dismiss** button — hides permanently (for "got it" or "not interested" cases)
- Dismissed items are not recoverable in the UI (kept in DB with dismissed=true but never shown)
- Added to top nav

## Matching / Edge Cases

- Artist name lookup: exact match against `artists.name` in DB; if iTunes returns an artist not in DB, skip
- Album title dedup: case-insensitive exact match against `albums.title` for that artist — already-owned albums won't appear
- Fuzzy matching deferred — can revisit if too many misses
- iTunes may return compilations or live albums — no filtering for now, dismiss as needed

## Out of Scope (for now)

- Scheduled/automatic refresh (manual refresh button is sufficient)
- "Undo dismiss" / dismissed items management UI
- MusicBrainz fallback for artists with poor iTunes coverage
- Links to purchase / stream (could add later)
