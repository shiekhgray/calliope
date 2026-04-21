# PRD: Track Share Links

## Goal

Allow a user to copy a direct link to a specific track — either from an album page
or a playlist page — and send it to someone. The recipient lands on the correct
context page (album or playlist), sees the track highlighted, and can play it after
logging in.

## Design Decisions

- **No new page or API endpoint** — share links are deep links to existing pages with
  a `?play={track_id}` query param. Everything needed is already fetched by those pages.
- **Two link contexts**:
  - Album context: `/calliope/albums/{album_id}?play={track_id}`
  - Playlist context: `/calliope/playlists/{playlist_id}?play={track_id}`
- **Auth gate**: if the recipient isn't logged in, `LoginPage` redirects to the target
  URL after a successful login (via a `?redirect=` param preserved through the flow).
- **Auto-play blocked by browsers** on fresh page load without prior user interaction.
  Instead of silently failing, highlight the target track row and show a prominent
  inline play button. If the user is already logged in and has interacted with the
  page (e.g. navigating from elsewhere in the app), auto-play fires normally.
- **Highlight style**: accent-colored left border + subtle background tint on the
  track row. Scrolls into view on mount. Highlight persists until the user plays
  a different track or navigates away.
- **Copy button placement**: a link icon button appears on hover at the right end of
  each track row (same hover zone as the existing add-to-playlist "+" button).
  Clicking it writes the correct context URL to the clipboard and briefly shows a
  "Copied!" tooltip.
- **Copy feedback**: tooltip replaces the icon for ~1.5s, then reverts. No toast — keep
  it local to the row.

## UI Layout

### Track row (on hover)
```
[ # ]  Track Title                  [ bitrate ]  [ plays ]  [ + ]  [ 🔗 ]
```
The link icon sits to the right of the existing "+" add-to-playlist button.

### Highlighted track row (after landing on a share link)
```
▌ Track Title                        [ bitrate ]  [ plays ]  [ + ]  [ 🔗 ]  ▶ Play
```
Left accent border + tinted background. A small "▶ Play" button appears inline at
the far right when the track isn't already playing (replaces the normal click-to-play
behavior for clarity).

## Auth Redirect Flow

1. Recipient opens `/calliope/albums/42?play=99`
2. `AuthContext` (or a route guard) detects no token → redirects to
   `/calliope/login?redirect=/calliope/albums/42?play=99`
3. `LoginPage` reads `?redirect=`, logs in, then calls `navigate(redirect)`
4. Album page loads, reads `?play=99`, highlights track 99

## Implementation

### 1. `LoginPage.jsx`
- Read `?redirect=` from `useSearchParams()`
- After successful login, `navigate(redirect ?? '/calliope/')` instead of hardcoded home

### 2. Route guard (or `AuthContext`)
- On unauthenticated access to any protected page, redirect to
  `/calliope/login?redirect={current path + search}`
- Currently login is voluntary (no hard guard). Add a lightweight check: if the page
  requires auth and no token exists, redirect. Album and playlist pages are read-only
  public candidates — but since streaming requires auth anyway, gate them.

### 3. `AlbumPage.jsx`
- Read `playTrackId = useSearchParams().get('play')`
- After tracks load, if `playTrackId` is set: scroll the matching row into view,
  apply `.track-row--highlighted` class
- Auto-play attempt: call `playTrack()` inside a `useEffect` — browser will silently
  block it if no prior interaction; highlight + inline play button serve as fallback

### 4. `PlaylistPage.jsx`
- Same as AlbumPage: read `?play=`, scroll + highlight + attempt auto-play

### 5. `AddToPlaylistMenu.jsx` or track row components
- Add a share icon button (`🔗` or a link SVG) alongside the existing "+" button
- `onClick`: build the URL based on current page context (album vs playlist), write
  to `navigator.clipboard.writeText(url)`, show "Copied!" tooltip for 1.5s
- The button must know whether it's in album context or playlist context — pass as a
  prop or read from `useLocation()`

### 6. CSS additions (`index.css`)
```css
.track-row--highlighted {
  border-left: 3px solid var(--accent);
  background: rgba(168, 85, 247, 0.08);
}

.track-share-btn {
  opacity: 0;
  transition: opacity 0.15s;
}

.track-row:hover .track-share-btn {
  opacity: 1;
}

.track-share-tooltip {
  font-size: 0.75rem;
  color: var(--accent);
  white-space: nowrap;
}
```

## Out of Scope

- Public (unauthenticated) playback — streaming always requires auth
- Sharing a whole album or playlist (just the track for now)
- Expiring or token-protected share URLs — the app is household-only
- Android deep link handling (can be added in Phase 5)
- Copying a share link from the Now Playing bar (nice-to-have, deferred)
