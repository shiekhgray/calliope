# PRD: Genre Tagging

## Problem

Genres are already scanned from ID3 tags but coverage is inconsistent — "Metal", "metal",
"Heavy Metal" floating around as separate entries, many albums untagged. There is no UI to
view, add, or remove genres, and no way to leverage the similarity engine or external sources
to suggest them.

## Goals

- View and edit genres on any album page (album-level writes, track-level storage).
- Three ways to get genre suggestions: fetch from Last.fm, suggest via similarity, or add manually.
- Per-artist genre fetch: hit one button on an artist page to pull Last.fm tags for all their
  albums at once. Covers both library albums and discovery cards.
- Genre data visible on the Releases page discovery cards (lazy Last.fm fetch, no library
  required).
- No bulk "tag everything" automation — the user browses to an artist or album and pulls
  data on demand.

## Out of Scope

- Track-level genre overrides (defer; album-level is sufficient for now).
- Writing genres back to ID3 tags on disk.
- Controlled vocabulary / genre hierarchy enforcement.
- Automatic background genre fetching.

---

## Data Model

No new tables. Genres are stored in the existing `track_genres` junction table at the track
level. Album-level operations write the same set of genres to every track in the album.

`genres.name` is normalized to lowercase on write. The `genres` table already enforces
`UNIQUE(name)`.

Last.fm API key stored in `.env` as `LASTFM_API_KEY`, read via `api/app/config.py`.

---

## API Endpoints

### Genre management (album-level)

```
GET    /albums/{id}/genres/fetch    ← Last.fm lookup by artist+album; returns suggestions[]
GET    /albums/{id}/genres/suggest  ← similarity engine; returns suggestions[]
POST   /albums/{id}/genres          ← auth required; {name} — adds genre to all tracks in album
DELETE /albums/{id}/genres/{genre_id} ← auth required; removes genre from all tracks in album
```

**Suggestion shape** (same for both fetch and suggest):
```json
[
  { "name": "gothic metal", "source": "lastfm", "weight": 87 },
  { "name": "darkwave",     "source": "lastfm", "weight": 61 }
]
```
For similarity suggestions `weight` is the count of tagged neighbors that carry that genre
(e.g. 8 out of 10 tagged neighbors → weight 8). For Last.fm it's their raw tag weight (0–100).

Suggestions are never auto-applied — the user accepts or dismisses each one in the UI.
Genres already on the album are excluded from suggestions.

### Artist-level fetch

```
GET /artists/{id}/genres/fetch
```

Calls Last.fm `artist.getTopTags` (one request). Returns the same suggestion shape.
Intended for the "fetch for this artist" button: applies accepted tags to **all albums**
by that artist in the library.

This endpoint does not write anything — it returns suggestions. The user accepts them via
the per-album `POST /albums/{id}/genres` calls (or a bulk-accept action described below).

### Genre autocomplete

```
GET /genres?q=   ← returns genres whose name contains q (case-insensitive), limit 20
```

Existing `/genres` endpoint can be extended with optional `?q=` filter.

### Releases genre fetch

```
GET /discover/{id}/genres/fetch
```

Calls Last.fm for a discovery entry (uses `album_title` + artist name from the joined
`Artist` record). Returns suggestion shape. Nothing is persisted — just shown on the card.
Discovery entries don't have tracks, so no writes happen here.

---

## Similarity Suggestion Algorithm

Goal: find the most common genres among acoustically similar, already-tagged tracks.

```
1. Fetch the track's feature vector from track_vectors.
   If not indexed, return 404 (no suggestion possible yet).

2. Walk outward through nearest neighbors (cosine distance, same z-score normalization
   used by /tracks/{id}/similar):
   - Stop when K tagged tracks have been found (default K = 10)
   - OR when M total neighbors have been checked (default M = 50)
   - Exclude tracks from the same album.

3. Collect all genre tags on the K found tracks.
   Tally by name (lowercase). Sort by count DESC.

4. Return top 3 by count, excluding genres already on this album.
```

K and M are query params (`?k=10&m=50`) so the caller can tune them. Default values are
good for sparse coverage; as the library gets tagged, lower M gives tighter suggestions.

The representative track for an album is the first indexed track (lowest track_number
that has a vector). If the album has no indexed tracks, return 404.

---

## Web UI Changes

### AlbumPage — genre section

Added below the album header, above the track table.

**Committed genres** — chips with ✕ (remove, auth gated). Shown always, empty state is fine.

**Pending suggestions** — chips in a distinct style (outlined/muted). Each has ✓ (accept)
and ✕ (dismiss). Suggestions are loaded on demand, not automatically.

**Controls** (auth gated):
- **Fetch** button — calls `GET /albums/{id}/genres/fetch`; replaces pending suggestions.
- **Suggest** button — calls `GET /albums/{id}/genres/suggest`; replaces pending suggestions.
- **Add** input — text field with autocomplete from `GET /genres?q=`; Enter or clicking a
  result calls `POST /albums/{id}/genres`; allows free-text new genres.

Accepting a pending chip calls `POST /albums/{id}/genres` and moves it to committed.
Dismissing a pending chip removes it from local state only (no API call).

### ArtistPage — per-artist fetch

A **"Fetch genres from Last.fm"** button added to the artist page header area (auth gated).
Calls `GET /artists/{id}/genres/fetch`. Shows returned tags as a pending chip list above
the albums grid with a note like "Apply to all albums by this artist."

A **"Apply to all"** action accepts all suggestions at once, firing `POST /albums/{id}/genres`
for each album × each accepted genre. A progress indicator shows how many albums were updated.
Individual chips can still be dismissed before applying.

This is the primary workflow for tagging a newly-curious artist in one shot.

### ReleasesPage — genre chips on cards

Each discovery card gets a **"Fetch genres"** link/button (visible always, not auth gated —
read-only). On click, calls `GET /discover/{id}/genres/fetch` and displays the returned tags
as plain read-only chips on the card. Tags are not persisted (no library entry exists yet).

Purpose: when browsing new releases to decide whether to add them to the library, the user
can see what genre Last.fm assigns without having to leave the page.

---

## Last.fm API Notes

- Free API key, register at last.fm/api. Add to `.env` as `LASTFM_API_KEY`.
- Endpoints used:
  - `artist.getTopTags` — for artist-level fetch (one call per artist)
  - `album.getInfo` — for album-level fetch; includes `toptags` in response
- Rate limit: 5 req/s on free tier. Not a concern for on-demand single fetches.
- If Last.fm returns no match (unknown artist/album), return empty suggestions `[]` — no error.
- Tag weight threshold: drop tags with weight < 10 to filter noise. Top 5 tags retained.

---

## Checklist

- [ ] `LASTFM_API_KEY` added to `.env.example` and `config.py`
- [ ] `GET /albums/{id}/genres/fetch` — Last.fm `album.getInfo` lookup
- [ ] `GET /albums/{id}/genres/suggest` — similarity k-NN genre tally
- [ ] `POST /albums/{id}/genres` — add genre to all tracks in album (auth)
- [ ] `DELETE /albums/{id}/genres/{genre_id}` — remove from all tracks in album (auth)
- [ ] `GET /genres?q=` — autocomplete filter added to existing endpoint
- [ ] `GET /artists/{id}/genres/fetch` — Last.fm `artist.getTopTags`
- [ ] `GET /discover/{id}/genres/fetch` — Last.fm lookup for discovery entry
- [ ] `AlbumPage.jsx` — genre chip section (committed + pending + controls)
- [ ] `ArtistPage.jsx` — "Fetch genres" button + pending chips + apply-to-all
- [ ] `ReleasesPage.jsx` — "Fetch genres" per card, read-only chips
- [ ] Normalize genre names to lowercase on write
- [ ] Smoke test: fetch Gothic Spirits 5, accept a suggestion, verify all tracks tagged
- [ ] Smoke test: artist fetch → apply all → verify albums updated
- [ ] Smoke test: suggest on untagged album with indexed tracks
