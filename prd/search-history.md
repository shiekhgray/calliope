# PRD: Per-User Search History

## Goal

Show each user a small cloud of links to recently-visited artists, albums, and tracks,
displayed persistently above the search bar on the search page. One click gets you back to
something you've looked at before without re-typing a query.

## Design Decisions

- **What's stored**: the exact entity clicked — artist, album, or track. `entity_type` drives
  both the link destination and the label format.
- **Track entries**: stored as tracks (not resolved to album). Displayed in the history cloud
  as a link to the parent album page. Clicking a track history entry plays the track AND
  navigates to the album page.
- **Track clicks in search results** (not history): play the track, record it in history,
  stay on the search page (no navigation).
- **Depth**: 10 most recent entries per user, deduplicated — revisiting something bumps it to
  the top rather than adding a duplicate.
- **Display**: always visible on the search page regardless of whether the search box has text;
  responsive link cloud in 2–3 columns depending on page width. Hidden entirely when history
  is empty.
- **Scope**: passive display only; no delete or clear UI for now.
- **Storage**: server-side, per user (history follows the user across devices).

## Data Model

New table: `search_history`

```sql
CREATE TABLE search_history (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    entity_type   VARCHAR(10) NOT NULL,   -- 'artist', 'album', or 'track'
    entity_id     INTEGER NOT NULL,
    visited_at    TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (user_id, entity_type, entity_id)
);

CREATE INDEX ix_search_history_user ON search_history (user_id, visited_at DESC);
```

No cached label column — names are fetched via join at query time. If an entity is deleted
from the library after a rescan, the join returns nothing and the entry is silently omitted.

Migration file: `0005_add_search_history.py`

SQLAlchemy model: `SearchHistory` in `models.py`

## API

### `GET /search/history`

Auth required. Returns the current user's 10 most recently visited entries, newest first.
Each entry is joined to its source table to get display names. Orphaned entries (entity
deleted from library) are excluded automatically by the inner joins.

Response:
```json
[
  { "entity_type": "artist", "entity_id": 12, "name": "Radiohead" },
  { "entity_type": "album",  "entity_id": 47, "name": "OK Computer", "artist_name": "Radiohead", "artist_id": 3 },
  { "entity_type": "track",  "entity_id": 201, "name": "Karma Police", "album_id": 47, "album_title": "OK Computer", "artist_name": "Radiohead" }
]
```

- Artist entries: `entity_id`, `name`
- Album entries: `entity_id`, `name`, `artist_id`, `artist_name`
- Track entries: `entity_id`, `name`, `album_id`, `album_title`, `artist_name`
  (track entries include `album_id` so the frontend can build the link to `/albums/:id`
  and call `playTrack()` with a fully-enriched track object)

Implementation note: the three entity types require three separate joins (artists, albums,
tracks→albums→artists). Use a UNION or fetch each type separately and merge in Python —
three small queries is fine given the 10-row limit.

### `POST /search/history`

Auth required. Records a visit. Upserts on `(user_id, entity_type, entity_id)` — if the row
already exists, update `visited_at` to now. After upsert, prune rows beyond the 10 most recent.

Request body:
```json
{ "entity_type": "track", "entity_id": 201 }
```

Response: `204 No Content`

The 10-row cap is enforced server-side on every write:
```sql
DELETE FROM search_history
WHERE user_id = :uid
  AND id NOT IN (
    SELECT id FROM search_history
    WHERE user_id = :uid
    ORDER BY visited_at DESC
    LIMIT 10
  )
```

## Frontend

### SearchPage changes

- On mount, fetch `GET /search/history` (React Query, `queryKey: ['search-history']`).
  Gated on `loggedIn` — `enabled: !!loggedIn`. Logged-out users see no history cloud.
- Render a `SearchHistory` component above the search input when `loggedIn` and history
  is non-empty.
- After any artist, album, or track click in search results, fire `POST /search/history`
  (fire-and-forget, errors silently swallowed) and invalidate `['search-history']` so the
  cloud updates.
- **Artist click in results**: record, navigate to `/artists/:id`.
- **Album click in results**: record, navigate to `/albums/:id`.
- **Track click in results**: record (`entity_type: 'track'`), call `playTrack()`, stay on
  search page.

### `SearchHistory` component

Displays a responsive CSS grid of links with a muted "Recent" heading above.

```css
.search-history {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 0.5rem;
  margin-bottom: 1.25rem;
}

.search-history a {
  /* pill or subtle chip style, truncated with ellipsis */
}
```

Link behaviour per entry type:
- **Artist** → `<Link to="/artists/:id">Artist Name</Link>`
- **Album** → `<Link to="/albums/:id">Artist — Album</Link>`
- **Track** → clicking calls `playTrack()` with the fully-enriched track object (album_id,
  album_title, artist_name all available from the history response), then navigates to
  `/albums/:album_id`. Label: `Artist — Track Title`.

Track entries in the history cloud need `playTrack()` from `PlayerContext` — import
`usePlayer` in the `SearchHistory` component (or pass `playTrack` as a prop).

### Auth guard

The search page is publicly usable. The history cloud only renders when `loggedIn` is true.

## Migration

File: `api/alembic/versions/0005_add_search_history.py`

Standard Alembic revision. `upgrade()` creates the table and index. `downgrade()` drops them.

## Out of Scope

- Storing raw query strings
- Delete / clear UI
- Any analytics or cross-user aggregation
