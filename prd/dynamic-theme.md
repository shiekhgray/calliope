# PRD: Dynamic Color Theme from Album Art

## Goal

The UI accent color shifts to match the dominant, most saturated color in the
current track's album art. Feels alive — each album has its own personality.
Falls back to the default purple when no art exists.

---

## Color Extraction

**Library**: [Vibrant.js](https://github.com/Vibrant-Colors/node-vibrant) (browser
build). Vibrant.js clusters pixels from an image and surfaces named swatches:
Vibrant, DarkVibrant, LightVibrant, Muted, DarkMuted, LightMuted.

The **Vibrant** swatch is used as the primary accent — it's specifically tuned to
find the most prominent, saturated color in the image, which matches the user's
intent exactly.

Extraction is done in the browser from the already-loaded album art `<img>` element
— no server changes, no extra network requests.

### Fallback chain

1. Vibrant swatch (preferred)
2. LightVibrant (if Vibrant is absent)
3. DarkVibrant (if both above absent)
4. Default purple `#a855f7` (no art, or no usable swatch found)

### Readability guard

The app uses a dark background. A very dark extracted color (e.g. near-black) would
be invisible as an accent. After extraction, enforce minimum lightness: if the
swatch's HSL lightness is below 40%, boost it to 40%. This keeps the accent visible
without discarding the hue entirely.

Similarly, if lightness exceeds 85% (too washed out on a dark background), cap at 85%.

---

## What Changes Color

Only the accent color — `--accent` in `index.css`. Everything that already uses
`var(--accent)` inherits the new color automatically:

- Active nav links
- Play button, scrubber thumb, progress fill
- Highlighted track rows (share link landing)
- Playlist drag handles, add-to-playlist hover
- "Scan complete" status text
- Radio mode toggle (when on)
- Now Playing current track label
- Search history chips

A secondary variable `--accent-dim` (the accent at 20% opacity) is also updated,
used for subtle backgrounds like the highlighted track row tint.

Nothing else changes — background, text, card colors remain fixed. The shift is
intentionally subtle.

---

## Transition Animation

CSS `@property` is used to register `--accent` as a typed color, enabling smooth
transitions between values:

```css
@property --accent {
  syntax: '<color>';
  inherits: true;
  initial-value: #a855f7;
}

:root {
  transition: --accent 0.6s ease;
}
```

Without `@property`, custom properties are untyped strings and cannot be interpolated.
With it, the browser smoothly interpolates between the old and new color across all
elements simultaneously. No per-element transition rules needed.

`@property` is supported in Chrome 85+, Firefox 128+, Safari 16.4+. For older
browsers, the color still updates — just without the fade. No JS animation fallback
needed; the snap is acceptable.

`--accent-dim` is derived in JS and updated alongside `--accent` — it also gets the
transition for free since it's registered the same way.

---

## Trigger

Color is recomputed each time `currentTrack` changes in `PlayerContext`. If the new
track is on the same album as the previous one, the album art is identical — Vibrant
still runs but will produce the same result. This is fast (cached image, ~10ms
extraction) and avoids a visible flash of the wrong color when skipping within an
album.

If `currentTrack` becomes null (playback stopped), accent resets to the default purple.

---

## Implementation

### Dependencies
- `vibrant` (npm) — browser build; ~50KB gzipped

### New hook: `web/src/hooks/useAlbumAccent.js`

```js
export function useAlbumAccent(albumArtUrl) {
  useEffect(() => {
    if (!albumArtUrl) {
      setAccent('#a855f7')
      return
    }
    Vibrant.from(albumArtUrl).getPalette().then((palette) => {
      const swatch =
        palette.Vibrant ?? palette.LightVibrant ?? palette.DarkVibrant
      if (!swatch) { setAccent('#a855f7'); return }

      // enforce lightness bounds
      const [h, s, l] = swatch.hsl
      const clampedL = Math.min(0.85, Math.max(0.40, l))
      const color = hslToHex(h, s, clampedL)

      setAccent(color)
    })
  }, [albumArtUrl])
}

function setAccent(hex) {
  const root = document.documentElement
  root.style.setProperty('--accent', hex)
  root.style.setProperty('--accent-dim', hex + '33')  // 20% opacity hex suffix
}
```

### `Layout.jsx` (or `PlayerContext.jsx`)

Call `useAlbumAccent(currentTrack?.albumArtUrl)` at the top level so it runs
once globally regardless of which page is displayed.

The album art URL is already available in `currentTrack` if `album_id` is included
(it is — see track enrichment requirements). Construct it as
`/calliope/api/albums/{album_id}/art`.

### `index.css`

Add `@property` declarations for `--accent` and `--accent-dim` at the top of the
file, before `:root`. Update `--accent-dim` initial value to match:

```css
@property --accent {
  syntax: '<color>';
  inherits: true;
  initial-value: #a855f7;
}

@property --accent-dim {
  syntax: '<color>';
  inherits: true;
  initial-value: #a855f733;
}

:root {
  transition: --accent 0.6s ease, --accent-dim 0.6s ease;
  /* existing vars... */
}
```

---

## Out of Scope

- Changing background or text colors (accent only)
- Server-side color extraction
- Per-user color preferences
- Palette display (showing the extracted swatches to the user)
- Adjusting contrast dynamically based on the extracted color's relationship to
  background (the lightness clamp is the only accessibility measure)
