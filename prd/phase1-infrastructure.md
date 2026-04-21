# Phase 1: Infrastructure

**Status: Complete**

## What Was Built

- `docker-compose.yml` — three services: `db` (postgres:16), `api` (Ubuntu 24.04 + Python venv), `web` (node:22-slim Vite dev server)
- `api/Dockerfile` — Ubuntu 24.04, Python venv at `/venv`
- `web/Dockerfile` — node:22-slim, runs `npm run dev`; `web/src` volume-mounted for HMR
- `nginx/calliope.conf` — drop-in location block; `proxy_buffering off`, `proxy_force_ranges on` for byte-range streaming
- `.env.example` — template for `DB_PASSWORD`, `SECRET_KEY`, `MUSIC_ROOT`

## URL Structure

All Calliope traffic lives under `/calliope/` so it coexists cleanly with other services on `dresdengray.com`.

| Path | Destination |
|------|-------------|
| `dresdengray.com/calliope/api/` | FastAPI (nginx strips `/calliope/api` prefix → API sees plain routes) |
| `dresdengray.com/calliope/` | Vite dev server (full path forwarded, Vite `base: '/calliope/'`) |

nginx config (`nginx/calliope.conf`):
- `/calliope/api/` block: `proxy_pass http://127.0.0.1:8000/` (trailing slash strips prefix)
- `/calliope` block: `proxy_pass http://127.0.0.1:5173` (no strip; includes WebSocket upgrade headers for HMR)

Web config:
- `vite.config.js`: `base: '/calliope/'`; proxy `/calliope/api` → API with prefix rewrite
- `BrowserRouter basename="/calliope"`
- axios `baseURL: '/calliope/api'`

FastAPI itself is unchanged — it still serves routes at `/artists`, `/albums` etc. because nginx strips the prefix.

## Key Decisions

- **Dev server in prod**: Vite dev server is sufficient; nginx static build deferred indefinitely.
- **Music volume is read-write**: Required for album art uploads writing `Folder.jpg` to album dirs. Do not revert to `:ro`.
- **API port**: Bound to `127.0.0.1:8000` (not exposed externally); nginx proxies it.
- **Web port**: `0.0.0.0:5173` — accessible from LAN via `dresdengray.com/calliope/`.

## Gotchas

- Docker CE 20.10 + Compose v2 plugin. Use `docker compose` (space). The `version:` header in docker-compose.yml is obsolete but harmless.
- `/etc/docker/daemon.json` explicitly sets `overlay2` — do not remove (needed after upgrade from 19.03/devicemapper).
- buildx installed manually at `~/.docker/cli-plugins/docker-buildx`.
- API container requires rebuild for any Python code change: `docker compose build api && docker compose up -d api`.
