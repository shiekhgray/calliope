# PRD: Spacebar Play/Pause

## Goal

Pressing spacebar anywhere in the app toggles playback — no need to click the
player bar. Feels like a native music app.

## Behavior

| State | Page | Result |
|---|---|---|
| Track is playing or paused | Any | Toggle play/pause |
| Nothing playing | AlbumPage | Play first track in the track list |
| Nothing playing | ArtistPage | Play first track in the top-tracks section |
| Nothing playing | PlaylistPage | Play first track in the playlist |
| Nothing playing | LibraryPage, SearchPage, ReleasesPage, other | No-op |

## Design Decisions

- **Input suppression**: do nothing if the event target is an `<input>`, `<textarea>`,
  or any element with `contenteditable`. Spacebar must type normally in search boxes,
  the playlist title field, the change-password modal, etc.
- **Default prevention**: call `e.preventDefault()` when spacebar is handled (prevents
  page scroll).
- **Global listener**: attach a single `keydown` listener on `window` in a top-level
  component or custom hook so it's always active regardless of which element has focus.
- **"First track" definition**:
  - AlbumPage: first entry in the `album.tracks` array (as returned by the API —
    already sorted by track_number)
  - ArtistPage: first entry in the `topTracks` array
  - PlaylistPage: first entry in the `playlist.entries` array (position order)
- **Track enrichment**: when calling `playTrack()` with the first track, ensure
  `album_id`, `album_title`, `artist_id`, `artist_name` are included — same
  requirement as all other `playTrack()` call sites.

## Implementation

### Custom hook: `useSpacebarPlayback(getFirstTrack)`

Create `web/src/hooks/useSpacebarPlayback.js`. Accepts a `getFirstTrack` callback
(returns a fully-enriched track object or `null`).

```js
export function useSpacebarPlayback(getFirstTrack) {
  const { isPlaying, togglePlayPause, playTrack } = usePlayer()

  useEffect(() => {
    const handler = (e) => {
      if (e.code !== 'Space') return
      const tag = e.target.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || e.target.isContentEditable) return
      e.preventDefault()

      if (isPlaying !== null) {   // something is loaded
        togglePlayPause()
      } else {
        const track = getFirstTrack?.()
        if (track) playTrack(track)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isPlaying, togglePlayPause, playTrack, getFirstTrack])
}
```

### `PlayerContext.jsx`

Expose `isPlaying` (null = nothing loaded, true = playing, false = paused) and
`togglePlayPause()` if not already available. `togglePlayPause` should call
`audio.play()` or `audio.pause()` based on current state.

### Page integration

Each page calls the hook with an appropriate `getFirstTrack` callback:

- **AlbumPage**: `() => enrichTrack(album.tracks[0], album)`
- **ArtistPage**: `() => topTracks[0]` (already enriched by the API)
- **PlaylistPage**: `() => playlist.entries[0]?.track` (needs enrichment — include
  `album_id`, `album_title`, `artist_id`, `artist_name` from the entry)
- **Other pages**: call hook with `null` or omit `getFirstTrack` — no-op when nothing playing

### CSS / UI

No visual changes needed. The existing play/pause button in `PlayerBar` reflects
state already.

## Out of Scope

- Other keyboard shortcuts (next/prev track, seek, volume)
- Spacebar behavior in modals (modals already trap focus to their own inputs,
  so the input-suppression check handles it)
