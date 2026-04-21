# PRD: Releases Page Filtering & Sorting

## Goal

The Releases page can surface a large backlog of albums (hundreds, when the user
hasn't checked in for years). Add a text filter and sort controls so the user can
quickly narrow down to a specific artist or browse by release year.

## Design Decisions

- **Client-side only** — the full list is already fetched in a single `GET /discover`
  call. No API changes required.
- **Filter scope**: text input matches against both artist name and album title
  (case-insensitive substring). Searching "angelzoom" finds all angelzoom releases;
  searching "live" finds albums with "live" in the title across all artists.
- **Sort options** (dropdown or segmented control):
  - Artist A–Z (default)
  - Newest first (release_date DESC, nulls last)
  - Oldest first (release_date ASC, nulls last)
- **Year range filter** (optional, lower priority): two number inputs (From / To year).
  If both blank, no year filtering applied. Either input alone also works as a one-sided
  bound. Entries with null release_date are shown regardless of year filter (can't exclude
  them confidently).
- **Filter/sort state is local React state** — not persisted, resets on page reload.
- **Result count**: show a muted count below the controls: "Showing X of Y releases".
  Hidden when no filter is active (X === Y).
- **Empty state**: if the filter produces zero results, show "No releases match your
  filter." instead of the standard empty-state messages.

## UI Layout

```
[ Releases ]                          [ Updated Apr 14, 2026 ]  [ Refresh ]

[ Filter by artist or album…       ]  [ Sort: Artist A–Z ▾ ]

                Showing 3 of 148 releases

[ card ] [ card ] [ card ] …
```

The filter input and sort dropdown sit on one row between the page header and the
grid. Year range inputs (if implemented) sit on a second row, collapsed/hidden by
default behind a "Filter by year" toggle to keep the initial UI clean.

## Implementation

All logic lives in `ReleasesPage.jsx` — no new files needed.

### State additions
```js
const [filterText, setFilterText] = useState('')
const [sortKey, setSortKey] = useState('artist')  // 'artist' | 'newest' | 'oldest'
// optional:
const [yearFrom, setYearFrom] = useState('')
const [yearTo, setYearTo] = useState('')
```

### Derived list
```js
const displayed = useMemo(() => {
  let list = [...discoveries]

  // text filter
  if (filterText.trim()) {
    const q = filterText.trim().toLowerCase()
    list = list.filter(
      (d) =>
        d.artist_name.toLowerCase().includes(q) ||
        d.album_title.toLowerCase().includes(q)
    )
  }

  // year filter (optional)
  if (yearFrom) list = list.filter((d) => !d.release_date || d.release_date.slice(0, 4) >= yearFrom)
  if (yearTo)   list = list.filter((d) => !d.release_date || d.release_date.slice(0, 4) <= yearTo)

  // sort
  if (sortKey === 'artist') {
    list.sort((a, b) => a.artist_name.localeCompare(b.artist_name) || a.album_title.localeCompare(b.album_title))
  } else if (sortKey === 'newest') {
    list.sort((a, b) => (b.release_date ?? '').localeCompare(a.release_date ?? ''))
  } else {
    list.sort((a, b) => (a.release_date ?? 'zzzz').localeCompare(b.release_date ?? 'zzzz'))
  }

  return list
}, [discoveries, filterText, sortKey, yearFrom, yearTo])
```

### CSS additions (`index.css`)

```css
.releases-controls {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.releases-filter-input {
  flex: 1;
  min-width: 200px;
}

.releases-count {
  font-size: 0.8rem;
  color: var(--muted);
  margin-bottom: 1rem;
}
```

## Out of Scope

- Persisting filter/sort state across page reloads
- Filtering by genre or format
- Multi-select artist filter (text input covers the use case)
- Server-side pagination (the full list fits in memory)
