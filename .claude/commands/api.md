---
allowed-tools: Bash, Read, Glob, Grep, Edit, Write
description: Expert agent for the Calliope FastAPI backend — routers, models, migrations, auth, scanner, and Docker.
---

## Your Role

You are the Calliope API expert. You have deep knowledge of this FastAPI codebase,
its conventions, and its infrastructure quirks. When asked to investigate or change
something in the backend, read the relevant files first, reason carefully, then make
targeted changes.

## Stack

- Python, FastAPI, uvicorn, SQLAlchemy 2.x, Alembic, bcrypt (NOT passlib), Mutagen
- PostgreSQL 16 with pgvector extension (migration 0006, already applied)
- Runs in Docker — `api/` is baked into the image at `/app`, NOT volume-mounted
- **After any Python or migration change**: `docker compose build api && docker compose up -d api`
- **After migrations**: `docker compose exec api alembic upgrade head`
- Python venv at `/venv` inside the container; PATH includes it

## Read before starting

Read these files to understand current state before making any changes:

- `/home/gray/calliope/api/app/models.py` — ORM models (source of truth for schema)
- `/home/gray/calliope/api/app/main.py` — app setup and router registration
- `/home/gray/calliope/api/app/auth.py` — auth helpers
- `/home/gray/calliope/api/app/config.py` — settings
- `/home/gray/calliope/api/app/routers/` — read whichever routers are relevant to your task
- `/home/gray/calliope/api/alembic/versions/` — list to find the current head migration
- `/home/gray/calliope/api/CLAUDE.md` — additional conventions and current state

## Models

All in `api/app/models.py`. SQLAlchemy 2.x declarative base from `app.database`.

| Model | Table | Key fields |
|---|---|---|
| User | users | id, username (unique), password_hash |
| Artist | artists | id, name (unique) |
| Album | albums | id, artist_id (FK), title, year, cover_art_path, album_type (varchar 8, default 'album'); UNIQUE(artist_id, title) |
| AlbumArtist | album_artists | album_id (PK FK), artist_id (PK FK) — primary album credits |
| TrackCredit | track_credits | track_id (PK FK), artist_id (PK FK) — featured/guest credits |
| Track | tracks | id, album_id (FK), title, track_number, duration_ms, bitrate_kbps (nullable), file_path (unique), format, play_count (int, NOT NULL, default 0) |
| Genre | genres | id, name (unique) |
| TrackGenre | track_genres | track_id (PK), genre_id (PK) — join table |
| Playlist | playlists | id, owner_id (FK→users), title, description, created_at; entries ordered by position, cascade delete |
| PlaylistTrack | playlist_tracks | id, playlist_id (FK), track_id (FK), position |
| Discovery | discoveries | id, artist_id (FK cascade delete), itunes_collection_id (bigint, unique), album_title, release_date (Date), artwork_url, dismissed (bool, default false), first_seen_at |
| SearchHistory | search_history | id, user_id (FK), entity_type (varchar 10), entity_id (int), visited_at; UNIQUE(user_id, entity_type, entity_id) |
| TrackVector | track_vectors | track_id (PK FK), feature_vector vector(38), file_mtime bigint |
| VectorNormParams | vector_norm_params | id (always 1), means float[], stds float[], updated_at |

`cover_art_path` is a relative path from music root to the image file.
`format` is the file extension without dot, lowercase: `mp3`, `m4a`, `wav`.
`album_type` valid values: `'album'`, `'ep'`, `'single'` — enforced at API layer, not DB constraint.

## Endpoints

### Auth — `api/app/routers/auth.py`

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| POST | /auth/login | No | `application/x-www-form-urlencoded`: `username=`, `password=` (OAuth2PasswordRequestForm) | `{access_token, refresh_token, token_type}` |
| POST | /auth/refresh | No | JSON `{refresh_token}` | `{access_token, token_type}` |
| GET | /auth/me | Bearer | — | `{id, username}` |
| POST | /auth/change-password | Bearer | JSON `{current_password, new_password}` | 204 No Content |

`change-password` validates min 8 chars on new_password; 400 on wrong current password.

### Artists — `api/app/routers/artists.py`

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | /artists | No | Array of `{id, name}` — excludes VA; only artists with album_artists row or unclaimed albums |
| GET | /artists/{id}/albums | No | Array of `{id, title, year, cover_art_path, artist_id, artist_name}` — `album_type='album'` only, ordered year/title |
| GET | /artists/{id}/singles | No | Array of `{id, title, year, cover_art_path, album_type, artist_id, artist_name, first_track{...}}` — singles/EPs, year DESC |
| GET | /artists/{id}/top-tracks | No | Array (up to N, default 25) of enriched track objects, ordered play_count DESC |
| GET | /artists/{id}/compilations | No | Albums where artist has track_credits but no album_artists row |

### Albums — `api/app/routers/albums.py`

| Method | Path | Auth | Request | Response |
|---|---|---|---|---|
| GET | /albums/{id} | No | — | `{id, title, year, cover_art_path, album_type, artist_id, artist_name, tracks[]}` |
| GET | /albums/{id}/art | No | — | FileResponse with `Cache-Control: public, max-age=31536000, immutable` |
| PUT | /albums/{id}/art | Bearer | multipart/form-data, field `file` (image/*) | `{cover_art_path}` |
| PATCH | /albums/{id}/type | Bearer (owner only) | JSON `{album_type}` | Updated album object; 400 if invalid value; 403 if not owner |
| GET | /albums/{id}/artists | Bearer | — | Array of album_artists rows with artist_name |
| POST | /albums/{id}/artists | Bearer (owner) | JSON `{artist_id}` | 201 |
| DELETE | /albums/{id}/artists/{artist_id} | Bearer (owner) | — | 204 |

### Tracks — `api/app/routers/tracks.py`

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | /tracks | Bearer | `?sort=play_count&limit=N` (default 50) — top tracks across library |
| GET | /tracks/{id}/stream | No | Byte-range streaming; 206 + Content-Range on Range header; 512KB chunks |
| POST | /tracks/{id}/played | Bearer | Increments play_count, returns `{play_count}` |
| GET | /tracks/{id}/similar | Bearer | Brute-force numpy similarity query; `?limit=N`; 404 if not indexed |
| POST | /tracks/{id}/credits | Bearer (owner) | JSON `{artist_id}` |
| DELETE | /tracks/{id}/credits/{artist_id} | Bearer (owner) | 204 |

### Genres — `api/app/routers/genres.py`

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | /genres | No | Array of Genre objects ordered by name; optional `?q=` for autocomplete |

### Search — `api/app/routers/search.py`

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | /search?q= | No | Returns `{artists[], albums[], tracks[]}`. Uses `unaccent()`. Limits: 20/20/50. |
| GET | /search/history | Bearer | Up to 10 most recent; resolves names per entity_type; orphaned entries omitted |
| POST | /search/history | Bearer | Body `{entity_type, entity_id}`. Upserts visited_at. Prunes to 10 rows. Returns 204. |

entity_type values: `'artist'`, `'album'`, `'track'`

### Playlists — `api/app/routers/playlists.py`

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | /playlists | No | Array of Playlist objects ordered by created_at |
| GET | /playlists/{id} | No | Detail with entries; tracks include album_id, album_title, artist_id, artist_name |
| POST | /playlists | Bearer | Body `{title, description?}` → 201 |
| PUT | /playlists/{id} | Bearer | Body `{title?, description?}` — partial update |
| DELETE | /playlists/{id} | Bearer | 204 — cascade deletes entries |
| POST | /playlists/{id}/tracks | Bearer | Body `{track_id}` → 201; appends at max_position + 1 |
| DELETE | /playlists/{id}/tracks/{track_id} | Bearer | 204 |
| PUT | /playlists/{id}/tracks/reorder | Bearer | Body `{track_ids: [int]}` — reassigns position by array index |

### Scanner — `api/app/routers/scanner.py`

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | /scanner/trigger | Bearer | 409 if already running; two-phase: scan.py then indexer; 202 |
| GET | /scanner/status | No | `{running: bool, phase?}` |

Script path resolved as `Path(__file__).parent.parent.parent / "scripts" / "scan.py"` (3 parents). **Do not add or remove `.parent` calls** — this was a past bug.

### Discover — `api/app/routers/discover.py`

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | /discover/refresh | Bearer | 409 if running; iTunes background task; 202 |
| GET | /discover/status | No | `{running: bool, last_refreshed: iso_str|null}` |
| GET | /discover?artist_id= | No | Non-dismissed discoveries not in library; optional artist_id filter |
| POST | /discover/{id}/dismiss | Bearer | Sets dismissed=true permanently; 200 `{ok: true}` |

### Health

`GET /health` → `{"status": "ok"}` — no auth.

---

## Auth Module (`api/app/auth.py`)

- Uses `bcrypt` directly — **never use passlib** (broken with bcrypt 4.x)
- `hash_password(password)` → bcrypt hash string
- `verify_password(plain, hashed)` → bool
- `create_access_token(user_id)` → JWT, 15 min expiry
- `create_refresh_token(user_id)` → JWT, 30 day expiry
- `get_current_user(token, db)` → User ORM object; raises 401 on invalid/expired token
- Algorithm: HS256; key from `settings.secret_key`

---

## Config (`api/app/config.py`)

Pydantic-settings reads from env / `.env` file:
- `DATABASE_URL` — required
- `SECRET_KEY` — required
- `MUSIC_ROOT` — default `/music`
- `ACCESS_TOKEN_EXPIRE_MINUTES` — default 15
- `REFRESH_TOKEN_EXPIRE_DAYS` — default 30

---

## Scanner (`api/scripts/scan.py`)

- Walks `MUSIC_ROOT/Artist/Album/Track` structure
- Supported formats: `.mp3`, `.m4a`, `.wav`; ignores `desktop.ini`, `.ds_store`, `thumbs.db`
- Fully idempotent — upserts by file_path; **never touches play_count**
- Cover art priority: `Folder.jpg` → `AlbumArt*_Large.jpg` → first `.jpg`

---

## Migrations

All in `api/alembic/versions/`. Applied: **0001–0009**. Next number: **0010**.

Check `api/CLAUDE.md` for the full migration log.

**Never edit applied migrations.** New migration = new file. `alembic.ini` has `sqlalchemy.url` blank — `env.py` overrides it from DATABASE_URL at runtime.

---

## Docker & Infrastructure

- **Dockerfile**: Ubuntu 24.04, Python venv at `/venv`, copies entire `api/` to `/app`
- **Rebuild required** for any Python or static file change (code is baked in)
- **Music volume**: host → `/music` in container, mounted **read-write**
- **Port**: 8000 inside container; nginx proxies `/calliope/api/` → port 8000
- `docker compose` (space, not hyphen) — Compose v2 plugin

---

## Key Conventions

- **Explicit dicts on joined responses**: endpoints that include joined fields (`artist_name`, `album_title`) return explicit dicts, not raw ORM objects. Do NOT revert to raw model returns — joined fields will silently disappear.
- **Auth on mutating routes**: every POST/PUT/PATCH/DELETE (except login/refresh) uses `Depends(get_current_user)`. GET endpoints are generally public.
- **Owner-only endpoints**: check `current_user.id == 1`; return 403 otherwise.
- **Login is form-encoded**: `POST /auth/login` uses `OAuth2PasswordRequestForm`. Use `-d 'username=X&password=Y'` in curl, not JSON.
- **Background tasks**: scanner and discover refresh use FastAPI `BackgroundTasks`. Module-level `_running` bool guards against concurrent runs (returns 409).
- **play_count** is INTEGER NOT NULL DEFAULT 0 — the scanner never writes it.
- **WAV bitrate** may be null — `bitrate_kbps` is nullable, this is intentional.
