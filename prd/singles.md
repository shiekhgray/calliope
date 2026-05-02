# Singles & EPs — Artist Page Inline Play

## Problem

The library contains single-track and short-form releases (singles, EPs) that are modeled as albums. They show up in the Albums grid on the artist page, which is misleading. There is also no way to play a single's track directly from the artist page without drilling into the album view.

---

## Goals

- Owner can label any album as `album` (default), `ep`, or `single` from the AlbumPage.
- Artist page gains a **Singles & EPs** section (conditional — hidden when empty), separate from the Albums grid.
- Each single/EP card shows album art with a ▶ overlay button; clicking it plays the track without leaving the artist page.
- Card art/title still links to the full album view (AlbumPage unchanged).
- Current "Singles, Remixes and Collaborations" section (compilation appearances) is renamed **Appears On** to avoid terminology collision.

## Non-goals

- Auto-detecting singles/EPs by track count.
- Changing the AlbumPage layout or behavior for singles/EPs.
- Separate "Singles" and "EPs" sections in the UI — both live under "Singles & EPs", sorted year desc.

---

## Schema — Migration 0009

```sql
ALTER TABLE albums ADD COLUMN album_type VARCHAR(8) NOT NULL DEFAULT 'album';
-- valid values: 'album', 'ep', 'single'
```

No DB-level check constraint — enforced at the API layer. All existing rows default to `'album'`.

---

## API

### `GET /artists/{id}/albums`
Unchanged in name. Now filters to `album_type = 'album'` only. Singles and EPs no longer appear in this list.

### `GET /artists/{id}/singles`
New endpoint. Returns albums where `album_type IN ('single', 'ep')`, ordered `year DESC, title ASC`. Each record embeds a `first_track` object so the frontend can call `playTrack()` without a second fetch:

```json
[
  {
    "id": 42,
    "title": "Cut to Black",
    "year": 2021,
    "cover_art_path": "...",
    "artist_name": "Lights",
    "artist_id": 7,
    "album_type": "single",
    "first_track": {
      "id": 301,
      "title": "Cut to Black",
      "duration_ms": 214000,
      "album_id": 42,
      "album_title": "Cut to Black",
      "artist_id": 7,
      "artist_name": "Lights"
    }
  }
]
```

### `PATCH /albums/{id}/type`
Owner-only. Body: `{"album_type": "album" | "ep" | "single"}`. Returns the updated album row. Returns 400 if the value is not one of the three allowed strings.

---

## Web

### ArtistPage section order (revised)

1. Top Tracks
2. Albums
3. **Singles & EPs** ← new, conditional
4. **Appears On** ← renamed from "Singles, Remixes and Collaborations"
5. Missing Releases

### Singles & EPs card

Same `.album-card` / `.album-grid` layout as Albums. One addition: a ▶ play button absolutely positioned over the album art (bottom-right corner, always visible — not hover-only). Clicking ▶ calls `playTrack(single.first_track, [single.first_track])`. Active state (this track is `currentTrack && isPlaying`) shows ⏸. The rest of the card (art + title area) is a `<Link to={/albums/${id}}>`.

```
┌──────────────────┐
│                  │
│  [album art]  ▶  │  ← overlay, bottom-right
│                  │
│ Cut to Black     │
│ 2021 · Single    │  ← show type badge
└──────────────────┘
```

Show a small type badge ("Single" / "EP") in the album-info row below the title so the distinction is visible even though they share a section.

### AlbumPage — type selector

Owner-only UI element in the album header area. Renders as a small clickable pill that cycles through `Album → EP → Single → Album`. Calls `PATCH /albums/{id}/type` on each click. Non-owners see a static label (or nothing).

### React Query keys

| Key | Data |
|---|---|
| `['artist-singles', id]` | Singles & EPs for one artist |

`PATCH /albums/{id}/type` invalidates `['artist-albums', id]` and `['artist-singles', id]`.

### Spacebar

No change. The artist page registers `topTracks[0]` as the first-track for spacebar; singles are not involved.

---

## Migration file

`api/alembic/versions/0009_add_album_type.py`
