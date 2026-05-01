# Track Credits — Many-to-Many Artist Attribution

## Problem

The music library contains collaborative albums where Lights appears as a co-equal primary artist (e.g. *Warehouse Summer* with i_o) and as a featured guest on individual tracks (e.g. *Empress of the Damned* on a GUNSHIP album). Neither case surfaces correctly on Lights' artist page. The root cause is that the current schema has one `album.artist_id` FK and one `track.track_artist_id` FK — both single-valued, neither able to express shared credit.

The same limitation will recur as the library grows (RAC's *Boy* is a near-term example: a producer album with a different featured vocalist on every track).

---

## Goals

- Collaboration albums appear on each credited artist's page.
- Combined-credit artist entries ("i_o & Lights") are retired from the browseable artist list without retagging MP3 files.
- VA compilations use the same mechanism as all other credits (retire `track_artist_id`).
- Credits are managed manually via the album page UI (no scanner automation for now).

---

## Schema — Migration 0008

```sql
CREATE TABLE album_artists (
  album_id  INTEGER REFERENCES albums(id)  ON DELETE CASCADE,
  artist_id INTEGER REFERENCES artists(id) ON DELETE CASCADE,
  PRIMARY KEY (album_id, artist_id)
);

CREATE TABLE track_credits (
  track_id  INTEGER REFERENCES tracks(id)  ON DELETE CASCADE,
  artist_id INTEGER REFERENCES artists(id) ON DELETE CASCADE,
  PRIMARY KEY (track_id, artist_id)
);

-- backfill: every existing album claims its current artist_id as a primary credit
INSERT INTO album_artists (album_id, artist_id)
SELECT id, artist_id FROM albums;

-- backfill: existing VA compilation track credits
INSERT INTO track_credits (track_id, artist_id)
SELECT id, track_artist_id FROM tracks WHERE track_artist_id IS NOT NULL;

ALTER TABLE tracks DROP COLUMN track_artist;
ALTER TABLE tracks DROP COLUMN track_artist_id;
```

The `album.artist_id` column is **not dropped**. The scanner continues to write it from the albumartist ID3 tag — it remains the authoritative display name for album cards. The new tables drive artist page attribution; `album.artist_id` drives display labels only.

---

## Artist List — Updated Filter

`GET /artists` currently filters out "Various Artists" by name. After this change, filter out artists whose albums have all been claimed by `album_artists` entries for other artists:

Show an artist if they have **at least one** `album_artists` row OR **at least one** album via `album.artist_id` with no `album_artists` rows at all.

```sql
SELECT DISTINCT ar.*
FROM artists ar
WHERE ar.name != 'Various Artists'
  AND (
    EXISTS (SELECT 1 FROM album_artists aa WHERE aa.artist_id = ar.id)
    OR EXISTS (
      SELECT 1 FROM albums al
      WHERE al.artist_id = ar.id
        AND NOT EXISTS (SELECT 1 FROM album_artists aa2 WHERE aa2.album_id = al.id)
    )
  )
ORDER BY ar.name;
```

Effect: once a combined-credit album (e.g. *Warehouse Summer*) has `album_artists` rows added for the solo artists, the combined-credit entry ("i_o & Lights") has no qualifying albums and drops off the list naturally. No rows are deleted; the entry persists as an anchor for the scanner.

---

## Artist Page — Updated Sections

### Albums
Albums where this artist has an `album_artists` entry.

```sql
SELECT DISTINCT al.*
FROM albums al
JOIN album_artists aa ON aa.album_id = al.id
WHERE aa.artist_id = :artist_id
ORDER BY al.year, al.title;
```

### Singles, Remixes and Collaborations
Albums where this artist has `track_credits` entries but **no** `album_artists` entry.

```sql
SELECT DISTINCT al.*
FROM albums al
JOIN tracks t ON t.album_id = al.id
JOIN track_credits tc ON tc.track_id = t.id
WHERE tc.artist_id = :artist_id
  AND NOT EXISTS (
    SELECT 1 FROM album_artists aa
    WHERE aa.album_id = al.id AND aa.artist_id = :artist_id
  )
ORDER BY al.year, al.title;
```

The existing "Appears On" section is replaced by this section.

---

## Album Page — Credit Management UI

Track rows gain a credits affordance visible to the owner only:

- Each track row shows credited artists as small chips (e.g. `feat. Lights`).
- Owner sees a `+` button to add a credit: opens an inline artist search (reuses existing `/search?q=` autocomplete), selects an existing artist, posts `POST /tracks/{id}/credits`.
- Clicking an existing chip opens a remove confirmation: `DELETE /tracks/{id}/credits/{artist_id}`.
- Album-level credits (for `album_artists`) are managed the same way at the album header level: owner sees which artists are credited as primary, can add or remove them.

The artist search must return existing artists only for now (no inline artist creation).

---

## API Changes

| Method | Path | Notes |
|---|---|---|
| `GET /artists` | (updated) | New filter query above |
| `GET /artists/{id}/albums` | (updated) | Query via `album_artists` |
| `GET /artists/{id}/compilations` | (updated) | "Singles & Collabs" query; rename response key optional |
| `GET /albums/{id}` | (updated) | Include `track_credits` per track in response |
| `POST /albums/{id}/artists` | new | Add `album_artists` entry (auth required) |
| `DELETE /albums/{id}/artists/{artist_id}` | new | Remove `album_artists` entry (auth required) |
| `POST /tracks/{id}/credits` | new | Add `track_credits` entry (auth required) |
| `DELETE /tracks/{id}/credits/{artist_id}` | new | Remove `track_credits` entry (auth required) |

---

## Test Case: RAC — *Boy*

*Boy* is an album by producer RAC where every track features a different vocalist. The albumartist tag is "RAC"; each track's artist tag names the featured vocalist. After this feature:

1. *Boy* gets an `album_artists` entry for RAC.
2. Each track gets a `track_credits` entry for its featured vocalist.
3. Each vocalist's artist page shows *Boy* in "Singles, Remixes and Collaborations".
4. RAC's page shows *Boy* in Albums.

This also replaces the VA compilation mechanism: RAC's *Boy* is structurally identical to a VA album from the attribution perspective but correctly attributed to a single album artist.

---

## Post-Migration Manual Cleanup

After the feature ships, re-attribute the known combined-credit albums:

| Album | Current `album.artist_id` | Add to `album_artists` | Add to `track_credits` |
|---|---|---|---|
| *Warehouse Summer* | i_o & Lights | i_o, Lights (all tracks) | — |
| *Empress of the Damned* | GUNSHIP, Lights feat. Tim Cappello | GUNSHIP | Lights on track 2916 |
| *Someone To Forget* | ARMNHMR & Lights | ARMNHMR, Lights (all tracks) | — |
| *Dead End* | Lights, MYTH | Lights, MYTH (all tracks) | — |

Once done, the combined-credit artist entries drop off the artist list automatically.

Note: `track_artist_id = 149` was set manually on these tracks during an earlier session. The migration backfill will move that to `track_credits`; no further action needed on those rows.

---

## Out of Scope

- Scanner auto-population of credits from ID3 tags.
- Retagging MP3 files or renaming folder structure.
- Credit roles (featured, remixer, producer) — single implicit "credited artist" for now.
- Creating new artists inline from the credits UI (search existing artists only).
