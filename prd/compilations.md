# PRD: Compilation Album Support

## Problem

Compilation albums (e.g. "Gothic Spirits 5") are stored in `Various Artists/<Album>/` with per-track ID3 `artist` tags but no `albumartist` tag. The scanner uses the `artist` tag for album ownership, so it creates N single-track albums (one per contributing artist) instead of one 34-track compilation. "Various Artists" is not surfaced in the Library, so there is currently no way to browse or play the full compilation.

## Desired Behaviour

- The full compilation is browsable and playable as a single album.
- Compilation albums are accessible via a dedicated **Compilations** page in the nav.
- Each track row in a compilation album view shows the contributing artist name, linked to that artist's page.
- Contributing artists (e.g. Therion) show an **"Appears On"** section on their artist page listing compilations they have a track on, linking to the compilation album view.
- "Various Artists" does **not** appear in the main artist library grid.

## Approach Overview

Two-phase fix: (1) tag the files on disk so the scanner has the information it needs, then (2) update the scanner, schema, API, and web UI to use it.

---

## Phase 1 — Tag the Files (one-time, manual or scripted)

All tracks inside `Various Artists/<Album>/` directories must be tagged:
```
albumartist = "Various Artists"
```
The per-track `artist` tag stays as-is (e.g. "Therion").

**Script**: `scripts/tag_compilations.py` — walks `/backup/calliope/music/Various Artists/`, finds all audio files whose parent directory is two levels deep (`Various Artists/<Album>/<track>`), and writes `albumartist = "Various Artists"` via Mutagen if not already set. Dry-run flag (`--dry-run`) prints what would change without writing. Report counts at the end.

**Duplicate files**: Gothic Spirits 5 (and possibly other compilations) also have individual tracks scattered under per-artist directories (e.g. `Therion/Gothic Spirits 5/01 Son Of The Staves Of Time.mp3`). These are exact duplicates of the tracks in `Various Artists/`. After tagging and rescanning, the user should manually delete these per-artist duplicate directories; the scanner does not auto-deduplicate by content.

---

## Phase 2 — Scanner Changes (`api/scripts/scan.py`)

### albumartist tag handling

When scanning a track, read the `albumartist` tag (Mutagen: `TPEA` for MP3, `aART` for M4A) in addition to `artist`. Use `albumartist` as the album's owning artist if present; otherwise fall back to `artist` as today.

EasyID3 key: `albumartist`. EasyMP4 key: `aART`.

### track_artist field

When the resolved track `artist` tag differs from the album's owning artist, store the track-level artist in a new `tracks.track_artist` (nullable VARCHAR) column. This is the contributing artist name for compilation tracks.

- For normal albums: `track_artist = NULL` (artist is implied by the album).
- For compilation tracks: `track_artist = "Therion"` etc.

### Migration

`api/alembic/versions/0007_add_track_artist.py`:
```sql
ALTER TABLE tracks ADD COLUMN track_artist VARCHAR;
```

---

## Phase 3 — API Changes

### New endpoint: GET /compilations

Returns all albums owned by the "Various Artists" artist, ordered by title.

```json
[
  {
    "id": 42,
    "title": "Gothic Spirits 5",
    "year": 2005,
    "cover_art_path": "Various Artists/Gothic Spirits 5/Folder.jpg",
    "track_count": 34
  }
]
```

### GET /albums/{id} — include track_artist

The existing endpoint already returns `tracks[]`. Add `track_artist` (nullable string) to each track object. No other change.

### GET /artists — exclude Various Artists

Filter out the artist named exactly `"Various Artists"` from the `/artists` response. This keeps the Library page clean.

### GET /artists/{id}/albums — add "appears on" query

New endpoint: `GET /artists/{id}/compilations`

Returns compilation albums (owned by Various Artists) that contain at least one track where `track_artist` matches this artist's name. Same shape as `/artists/{id}/albums`.

```json
[
  {
    "id": 42,
    "title": "Gothic Spirits 5",
    "year": 2005,
    "cover_art_path": "...",
    "artist_id": <various-artists-id>,
    "artist_name": "Various Artists"
  }
]
```

---

## Phase 4 — Web UI Changes

### New page: CompilationsPage (`web/src/pages/CompilationsPage.jsx`)

Route: `/compilations`

- Same grid layout as the artist album grid (reuse `.releases-grid` / album card CSS or artist albums grid).
- Each card: cover art, album title, year, track count.
- Clicking a card navigates to `/albums/{id}` (the existing album route — see below).
- Added to the top nav alongside Artists, Playlists, Releases.

### Album page — compilation mode (`web/src/pages/AlbumPage.jsx`)

When any track in the album has a non-null `track_artist`, the album is a compilation. In that case:

- Show an **Artist** column in the track table (between track number and title, or after title).
- Each artist name in that column is a link to `/artists/{artist_id}` — requires resolving artist_id from name. See resolution note below.
- Album header shows "Various Artists" as the artist (no link, since VA is filtered from the library).
- Otherwise the page is identical to today.

**Artist name → id resolution**: The track objects returned by `GET /albums/{id}` include `track_artist` (name string) but not a track_artist_id. Two options — pick one at implementation time:
  - **Option A (simple)**: render the name as plain text (no link) — sufficient for first pass.
  - **Option B (linked)**: add `track_artist_id` (nullable FK → artists) to the tracks schema and populate it in the scanner. Enables proper links from the compilation album view to each artist's page.

  Recommend Option B if the scanner work is straightforward; Option A if FK lookup adds complexity.

### Artist page — "Appears On" section (`web/src/pages/ArtistPage.jsx`)

Below the existing albums grid, add an **"Appears On"** section. Uses `GET /artists/{id}/compilations`. Only renders when the list is non-empty. Same card style as the albums grid. Cards link to `/albums/{id}`.

---

## Schema Summary

```
tracks   +  track_artist  VARCHAR  NULL    -- contributing artist name; NULL for non-compilation tracks
tracks   +  track_artist_id  INT   NULL FK → artists  -- (Option B only)
```

No changes to `albums` or `artists` tables — "Various Artists" is just another artist record.

---

## Out of Scope

- Detecting compilations automatically without tags (directory-name heuristics).
- Moving or renaming files on disk.
- Surfacing "Various Artists" as a browsable artist anywhere.
- Multi-disc compilations (track numbering treated as flat list).
- MusicBrainz or other metadata enrichment.

---

## Checklist

- [ ] `scripts/tag_compilations.py` written and tested with `--dry-run`
- [ ] Tags applied to all `Various Artists/` files on disk
- [ ] Per-artist duplicate dirs deleted
- [ ] Migration `0007_add_track_artist.py` written
- [ ] Scanner reads `albumartist`; populates `track_artist` (and optionally `track_artist_id`)
- [ ] `GET /compilations` endpoint
- [ ] `GET /albums/{id}` returns `track_artist` per track
- [ ] `GET /artists` excludes "Various Artists"
- [ ] `GET /artists/{id}/compilations` endpoint
- [ ] `CompilationsPage.jsx` + nav link
- [ ] `AlbumPage.jsx` compilation mode (Artist column)
- [ ] `ArtistPage.jsx` "Appears On" section
- [ ] Rescan after tagging; verify Gothic Spirits 5 shows all 34 tracks
- [ ] Smoke test: Therion artist page shows "Appears On" → Gothic Spirits 5
