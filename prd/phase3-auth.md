# Phase 3: Auth

**Status: Complete**

## What Was Built

- JWT access tokens (15 min) + refresh tokens (30 days) via `python-jose`
- `POST /auth/login` — returns access + refresh tokens
- `POST /auth/refresh` — returns new access token
- `GET /auth/me` — returns `{id, username}` for active session
- `POST /auth/change-password` — requires `current_password` + `new_password` (min 8 chars)
- `get_current_user` FastAPI dependency — applied to all mutating routes and scanner trigger
- `api/scripts/seed_users.py` — seeds users: `docker compose exec api python scripts/seed_users.py <user> <pass>`

## Users

- id=1: owner
- id=2: `thefacesblur` — seeded with temporary password, should be changed via change-password

## Key Decisions

- **bcrypt directly** — passlib 1.7.4 is broken with bcrypt 4.x (`AttributeError` on `__about__`). Auth uses `bcrypt.hashpw` / `bcrypt.checkpw` directly.
- No external identity provider — two users in the `users` table is sufficient.
- `owner_id` in playlists router uses auth token user, not hardcoded.

## Web Auth Flow

- `AuthContext` stores access token + username in localStorage
- Auto-refreshes on 401 via axios interceptor in `api/client.js`
- Calls `GET /auth/me` on load if token exists but username is missing (handles pre-existing sessions)
