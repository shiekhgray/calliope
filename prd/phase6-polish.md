# Phase 6: Polish & Search

**Status: Not started**

## Items

### Genre Management UI
Genres are already scanned from ID3/M4A tags and stored in `genres` / `track_genres`. What's missing is a UI to view and assign genres to tracks.
- Genre filter/browse page (list genres → tracks in that genre)
- Assign/remove genres on the album track table (inline tag editor)
- API endpoints needed: `PUT /tracks/{id}/genres`, `DELETE /tracks/{id}/genres/{genre_id}`

### Color-Coded Pages from Album Art
Extract a dominant color from each album's `Folder.jpg` and use it to tint the artist/album page header. Fall back to the default purple accent when no art is available.
- Options: server-side extraction (Pillow, store hex in DB) or client-side (Canvas API)
- Server-side preferred — compute on scan, store as `dominant_color` column on `albums`

### Search Improvements
Current search is a basic ILIKE on title/name fields. Possible improvements:
- Weighted ranking (exact match > prefix > substring)
- Search within playlist track lists
- PostgreSQL `pg_trgm` trigram index for fuzzy/typo-tolerant matching

### Performance Review
- Query audit: N+1 checks on artist/album/playlist endpoints
- Add indexes where missing (currently: artists.name, albums.title, tracks.file_path)
- Profile scanner on large rescans

### PostgreSQL Backup Strategy
- `pg_dump` cron job writing to a backup directory on the host
- Retention policy (e.g. keep last 7 daily dumps)
- Document restore procedure in README

### Album Art Edge Cases
- Albums with no art and no fallback: show a generated placeholder (initials, color hash)
- Art served with long cache headers — `?v=N` cache-bust already handled on upload
