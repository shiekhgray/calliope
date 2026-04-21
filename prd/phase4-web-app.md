# Phase 4: Web App

**Status: Complete**

## What Was Built

React + Vite app running as a Docker container (dev server, HMR via src volume mount).

### Pages

- **Library** (`/`) — artist list
- **Artist** (`/artists/:id`) — top 10 tracks section + albums grid
- **Album** (`/albums/:id`) — album header with art upload overlay + track table
- **Search** (`/search`) — searches artists, albums, tracks
- **Playlists** (`/playlists`) — list, create, delete
- **Playlist** (`/playlists/:id`) — detail view, remove tracks, drag-and-drop reorder
- **Releases** (`/releases`) — iTunes-powered new release discovery (see `releases-discovery.md`)

### Components

- `Layout.jsx` — top nav + player bar shell; UserMenu with change-password modal + Rescan Library
- `PlayerBar.jsx` — fixed bottom bar; volume popover; album/artist links in now-playing
- `AddToPlaylistMenu.jsx` — "+" popover on every track row
- `ChangePasswordModal.jsx`

### Player

- Singleton `Audio` element in `PlayerContext`
- Queue, play/pause, seek, volume
- `onended` fires `POST /tracks/{id}/played` (fire-and-forget, errors swallowed)
- Skip does not increment play count — only natural completion

### Key Features

- **Track enrichment**: always pass `album_id`, `album_title`, `artist_id`, `artist_name` to `playTrack()` — PlayerBar uses these for links
- **Album art upload**: hover overlay on album page; writes `Folder.jpg`; cache-busts with `?v=N` local state
- **Bitrate**: shown in muted right-aligned column on track rows
- **Play count**: shown on track rows (blank when 0); top 10 on artist page shuffled at zero, bubbles up with plays
- **Playlist reorder**: native HTML5 DnD; optimistic local state; reverts on API error
- **Rescan Library**: user menu; polls `/scanner/status` every 2s; shows "Scan complete" for 3s

## Key Decisions

- Dark theme, purple accent (`#a855f7`)
- Vite proxy: `/api/*` → `http://api:8000` in Docker; `http://localhost:8000` locally
- `allowedHosts` includes `dresdengray.com`
- Genre tagging UI deferred (genres exist in DB and are scanned, just no UI to assign them)
- Nginx static build config deferred — dev server is sufficient
