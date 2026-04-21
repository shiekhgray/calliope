# PRD: Missing Releases Section on Artist Page

## Goal

When viewing an artist's page, show a "Missing Releases" section listing albums that
iTunes knows about but aren't in the local library yet. The section only renders when
there's something to show. Per-card dismiss works the same as on the Releases page.

## Design Decisions

- **Only renders when non-empty** — no section header, no empty state, no placeholder.
  If the artist has no discovery data or everything is dismissed/owned, the section is
  invisible. Zero noise for artists where you're up to date.
- **Dismiss is permanent** — same behaviour as the Releases page. Dismissed entries
  are gone from both this section and the main Releases page.
- **No refresh button** — refresh is a global operation on the Releases page. The
  artist page just reads whatever data is already in the DB.
- **Auth guard on dismiss only** — the section is visible to logged-out users (read-only).
  The Dismiss button is only shown when `loggedIn` is true (same pattern as other
  mutating actions in the app).
- **Card style** — reuse the existing `.release-card` / `.releases-grid` CSS from the
  Releases page. No new component needed; the markup is straightforward enough to
  inline in ArtistPage.jsx.

## API Change

### `GET /discover` — add optional `artist_id` query param

```
GET /discover?artist_id=42
```

- If `artist_id` is provided, filter results to that artist only.
- Existing behaviour (no param → all artists) is unchanged.
- Same response shape as the current endpoint.

Backend change is small: add `artist_id: int | None = None` as a Query param in
`get_discoveries()` and add a `.filter(models.Discovery.artist_id == artist_id)` when
it's present, before the loop.

No new endpoint needed.

## Frontend

### ArtistPage.jsx changes

Add a second `useQuery` call for the artist's missing releases:

```js
const { data: missingReleases = [] } = useQuery({
  queryKey: ['discoveries', 'artist', id],
  queryFn: () => api.get('/discover', { params: { artist_id: id } }).then((r) => r.data),
})
```

Add a dismiss mutation that invalidates both the artist-scoped and global discoveries
queries when it fires:

```js
const qc = useQueryClient()
const dismissMutation = useMutation({
  mutationFn: (discoveryId) => api.post(`/discover/${discoveryId}/dismiss`),
  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ['discoveries', 'artist', id] })
    qc.invalidateQueries({ queryKey: ['discoveries'] })
  },
})
```

Render the section between the Albums heading and the album grid, only when
`missingReleases.length > 0`:

```jsx
{missingReleases.length > 0 && (
  <section className="missing-releases">
    <h3 className="section-heading">Missing Releases</h3>
    <div className="releases-grid">
      {missingReleases.map((d) => (
        <div key={d.id} className="release-card">
          {d.artwork_url
            ? <img src={d.artwork_url} alt={d.album_title} />
            : <div className="release-card-no-art" />}
          <div className="release-card-body">
            <div className="release-card-title">{d.album_title}</div>
            {d.release_date && (
              <div className="release-card-year">{d.release_date.slice(0, 4)}</div>
            )}
            {loggedIn && (
              <button
                className="release-dismiss-btn"
                onClick={() => dismissMutation.mutate(d.id)}
                disabled={dismissMutation.isPending}
              >
                Dismiss
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  </section>
)}
```

`loggedIn` comes from `useAuth()` — already available in the app via `AuthContext`.

### Section placement

```
[ Artist Name ]
  Top Tracks
  Albums
  Missing Releases   ← new, only when non-empty
  [ album grid ]
```

Placing it between the Albums heading and grid keeps the library content primary and
the "what you don't have" secondary.

Actually, place it *after* the album grid so owned content leads:

```
[ Artist Name ]
  Top Tracks
  Albums
  [ album grid ]
  Missing Releases   ← after owned albums
```

## No New CSS Required

The section reuses `.releases-grid`, `.release-card`, `.release-card-body`,
`.release-card-title`, `.release-card-year`, `.release-dismiss-btn`, and
`.release-card-no-art` already defined in `index.css`.

## Out of Scope

- Inline "refresh for this artist only" — full refresh is on the Releases page
- Linking out to iTunes or a purchase page
- "Undo dismiss" or dismissed items management
