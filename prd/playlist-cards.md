# PRD: Playlist Cards

## Goal

Replace the current flat playlist list with rich playlist cards. Each card shows
a 2×2 collage of album art drawn from the playlist's most representative tracks,
a preview of the first few track titles, and (once genre tagging ships) the top
genre chips. The card is fully clickable and navigates to the playlist page.

## Design Decisions

- **Centroid-based track selection**: "most quintessential" means closest to the
  centroid of all playlist track vectors — the tracks that best represent the
  overall sound of the playlist. Same normalization pipeline as the existing
  similarity query (z-score → L2-normalize → cosine similarity).
- **Unique album art**: once a `cover_art_path` (equivalently, `album_id`) is
  selected for a slot, it is excluded from subsequent slots. This prevents a
  playlist of one artist's albums from showing the same cover four times.
- **Fallback when vectors are sparse**: if fewer than 4 tracks have indexed
  vectors, fill remaining slots from the playlist's positional order (first
  tracks first), skipping already-represented albums and tracks with no art.
- **Fallback when no vectors at all**: use positional order entirely.
- **Art holes are fine**: if the playlist has fewer than 4 unique album arts,
  show however many are available. Empty slots are not padded with placeholder
  tiles — the grid just has fewer images.
- **All data in the list endpoint**: `GET /playlists` returns everything the
  card needs. No separate per-playlist requests on the list page.
- **Genre chips are conditional**: the card renders a chip row only when
  `top_genres` is non-empty. Empty until genre tagging is implemented — the
  card structure is designed for them from day one so no retrofit is needed.
- **Vertical card list**: full-width cards stacked vertically, not a grid.
  Keeps the track-title preview readable at any viewport width.
- **Delete affordance**: small `✕` button in the top-right corner of the card,
  visible on hover, stops click propagation so it doesn't navigate. Matches
  existing UX pattern. Will integrate naturally with the ownership check from
  playlist-permissions.md once that ships.

## Algorithm: Quintessential Track Selection

Runs server-side per playlist during `GET /playlists`. Norm params are fetched
once and reused across all playlists in the request.

```python
def quintessential_art_tracks(playlist, db, norm_params, n=4):
    entries = playlist.entries  # ordered by position
    track_ids = [e.track_id for e in entries]
    if not track_ids:
        return []

    # Fetch vectors only for tracks in this playlist
    vectors = {
        tv.track_id: tv.feature_vector
        for tv in db.query(models.TrackVector)
                     .filter(models.TrackVector.track_id.in_(track_ids))
                     .all()
    }

    # Build lookup: track_id → (album_id, cover_art_path)
    art_map = {}
    for entry in entries:
        t = entry.track
        cap = t.album.cover_art_path if t.album else None
        art_map[t.id] = (t.album_id, cap)

    # Score vectorized tracks by similarity to centroid
    ranked_ids = []
    if vectors:
        vids = list(vectors.keys())
        matrix = np.array([vectors[tid] for tid in vids], dtype=np.float32)

        if norm_params:
            means = np.array(norm_params.means, dtype=np.float32)
            stds  = np.array(norm_params.stds,  dtype=np.float32)
            stds[stds == 0] = 1.0
            matrix = (matrix - means) / stds

        row_norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        row_norms[row_norms == 0] = 1.0
        matrix /= row_norms

        centroid = matrix.mean(axis=0)
        c_norm = np.linalg.norm(centroid)
        if c_norm > 0:
            centroid /= c_norm

        sims = matrix @ centroid
        order = np.argsort(sims)[::-1]
        ranked_ids = [vids[i] for i in order]

    # Fill remaining from positional order (tracks without vectors)
    unvectorized = [tid for tid in track_ids if tid not in vectors]
    candidate_ids = ranked_ids + unvectorized

    # Pick up to n, enforcing unique album_id and non-null cover_art_path
    selected = []
    seen_albums = set()
    for tid in candidate_ids:
        if len(selected) >= n:
            break
        album_id, cap = art_map.get(tid, (None, None))
        if not cap or album_id in seen_albums:
            continue
        seen_albums.add(album_id)
        selected.append({"track_id": tid, "album_id": album_id, "cover_art_path": cap})

    return selected
```

## API Changes

### `GET /playlists` — enriched response

Each playlist object gains four new fields:

```json
{
  "id": 1,
  "title": "Sunday Drive",
  "description": null,
  "created_at": "...",
  "owner_id": 1,
  "track_count": 24,
  "art_tracks": [
    { "track_id": 17, "album_id": 5, "cover_art_path": "Artist/Album/Folder.jpg" },
    { "track_id": 42, "album_id": 11, "cover_art_path": "Artist/Album2/Folder.jpg" },
    { "track_id": 99, "album_id": 3, "cover_art_path": "Artist2/Album/Folder.jpg" },
    { "track_id": 7,  "album_id": 22, "cover_art_path": "Artist3/Album/Folder.jpg" }
  ],
  "preview_tracks": ["Intro", "Fast Lane", "Night Ride"],
  "top_genres": []
}
```

- `art_tracks`: 0–4 entries from the quintessential algorithm above.
- `preview_tracks`: titles of the first 3 entries (by `position`), ordered
  ascending. Empty list if the playlist has no tracks.
- `top_genres`: top 4 genre names by frequency across all tracks in the playlist,
  ordered by count descending. Empty list until genre tagging is implemented.
- `track_count`: total number of entries.

Norm params are fetched once at the top of the handler and passed through. If
`vector_norm_params` has no row yet, the centroid step still runs (un-normalized)
and degrades gracefully.

No new endpoint needed. `GET /playlists/{id}` (detail page) is unchanged.

## Web UI Changes

### `PlaylistsPage.jsx`

Replace the `<ul className="playlist-list">` with a `<div className="playlist-cards">`.
Each playlist renders as a `<PlaylistCard>` component (defined in the same file or
extracted to `components/PlaylistCard.jsx`).

The create form and `+ New playlist` button in the header are unchanged.

### `PlaylistCard` component

```
┌─────────────────────────────────────────────────────────────┐
│  ┌──────┬──────┐                                       [✕]  │
│  │ art  │ art  │  Sunday Drive                              │
│  ├──────┼──────┤  Intro · Fast Lane · Night Ride            │
│  │ art  │ art  │  [electronic]  [ambient]  [post-rock]      │
│  └──────┴──────┘                                            │
└─────────────────────────────────────────────────────────────┘
```

- The entire card is a `<Link to={/playlists/${id}}>` — no nested `<a>`.
  The `✕` delete button uses `e.stopPropagation()` and its own `onClick`.
- **2×2 art grid** (left): four 60×60px `<img>` tiles arranged in a CSS grid.
  Each `src` is `/calliope/api/albums/{album_id}/art`. `onError` hides broken
  images with `display:none` so the layout degrades without blank boxes.
  When `art_tracks.length < 4`, the grid simply has fewer images (no placeholders).
- **Text block** (right of art):
  - Playlist title in medium weight
  - Track preview: `preview_tracks` joined with ` · ` separator, muted color,
    single line truncated with `text-overflow: ellipsis`
  - Genre chips: only rendered when `top_genres.length > 0`; each chip is a
    small pill styled like search-history chips (reuse `.search-history-chip`
    or create `.genre-chip`)
- **`✕` button**: absolute-positioned top-right; opacity 0 at rest, 1 on card
  hover; fires `deleteMutation` on click.

### CSS additions (`index.css`)

```css
.playlist-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 16px;
}

.playlist-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--surface2);
  text-decoration: none;
  color: inherit;
  transition: background 0.15s;
}

.playlist-card:hover {
  background: var(--surface3);
}

.playlist-card-art {
  display: grid;
  grid-template-columns: 60px 60px;
  grid-template-rows: 60px 60px;
  gap: 2px;
  border-radius: 4px;
  overflow: hidden;
  flex-shrink: 0;
  background: var(--surface3);  /* visible when art_tracks is empty */
}

.playlist-card-art img {
  width: 60px;
  height: 60px;
  object-fit: cover;
  display: block;
}

.playlist-card-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.playlist-card-title {
  font-weight: 500;
  color: var(--text1);
}

.playlist-card-tracks {
  font-size: 0.8rem;
  color: var(--text3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.playlist-card-genres {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 2px;
}

.playlist-card-delete {
  position: absolute;
  top: 8px;
  right: 8px;
  opacity: 0;
  transition: opacity 0.15s;
  background: none;
  border: none;
  color: var(--text3);
  cursor: pointer;
  font-size: 0.75rem;
  padding: 2px 4px;
}

.playlist-card:hover .playlist-card-delete {
  opacity: 1;
}
```

## Out of Scope

- Showing the track count on the card (could be added as a subtle `24 tracks`
  suffix, deferred — keep the card clean for now)
- Lazy/paginated loading of the playlist list (not needed at this scale)
- Editing playlist title inline from the card (handled on the detail page)
- Playlist description on the card (usually null; not worth the space)
- The `✕` button respecting ownership (will fall out naturally when
  playlist-permissions.md ships — the endpoint will return 403 and the button
  can be hidden based on `owner_id` matching the current user)
