# PRD: Playlist Permissions

## Goal

Give playlist owners granular control over who can view and who can edit each
playlist. Currently all playlists are fully public and any logged-in user can
mutate any playlist. This adds per-playlist view and edit access control.

## Design Decisions

- **Two independent axes**: view access and edit access, each with three modes:
  `owner` (only creator), `users` (specified user list), `everyone` (all
  authenticated users).
- **Owner always has both**: regardless of any setting, the creating user always
  retains full view + edit + delete rights.
- **Edit implies view**: a user granted edit access can always view the playlist,
  even if `view_mode` is `owner`. The backend enforces this at check time.
- **Auth required everywhere**: unauthenticated requests get 401 on all playlist
  endpoints. There is no public playlist access — streaming requires auth anyway.
- **Ownership is not transferable**: only the owner can change permissions or
  delete the playlist. Editors can only modify tracks and metadata (title,
  description).
- **Defaults for new playlists**: `view_mode=everyone`, `edit_mode=owner`. This
  preserves existing behaviour — playlists are visible to all users by default,
  but only the creator can edit.
- **Existing playlists**: migrated with the same defaults (`everyone`/`owner`) so
  nothing breaks on deploy.
- **No public (unauthenticated) access**: even `view_mode=everyone` still requires
  a valid session token.
- **`DELETE` is owner-only**: no matter what `edit_mode` is set to.

## Database Changes

### New columns on `playlists`

```sql
view_mode  VARCHAR(10) NOT NULL DEFAULT 'everyone'
  -- 'owner' | 'users' | 'everyone'
edit_mode  VARCHAR(10) NOT NULL DEFAULT 'owner'
  -- 'owner' | 'users' | 'everyone'
```

### New join tables

```sql
CREATE TABLE playlist_viewers (
    playlist_id INTEGER REFERENCES playlists(id) ON DELETE CASCADE,
    user_id     INTEGER REFERENCES users(id)     ON DELETE CASCADE,
    PRIMARY KEY (playlist_id, user_id)
);

CREATE TABLE playlist_editors (
    playlist_id INTEGER REFERENCES playlists(id) ON DELETE CASCADE,
    user_id     INTEGER REFERENCES users(id)     ON DELETE CASCADE,
    PRIMARY KEY (playlist_id, user_id)
);
```

Rows in these tables are only meaningful when the corresponding mode is `users`.
They are left in place but ignored when the mode is `owner` or `everyone`, so
changing the mode back to `users` restores the previously saved list.

### Alembic migration

`0008_add_playlist_permissions.py` — adds the two columns + two tables.

## API Changes

### New endpoint: `GET /users`

Auth required. Returns all users as `[{id, username}]`. Needed by the frontend
to populate the user-picker in the permissions panel. No sensitive fields.

### `GET /playlists` — now auth required

Returns only playlists the current user **can view** (applying permission check).
Each playlist object gains:

```json
{
  "id": 1,
  "title": "...",
  "description": "...",
  "created_at": "...",
  "owner_id": 1,
  "view_mode": "everyone",
  "edit_mode": "owner",
  "viewer_ids": [],
  "editor_ids": []
}
```

### `GET /playlists/{id}` — now auth required + permission check

Returns 403 if the current user cannot view the playlist. Same shape as above
plus the `entries` array.

### `POST /playlists` — accepts permission fields

```json
{
  "title": "My Mix",
  "description": null,
  "view_mode": "everyone",
  "edit_mode": "owner",
  "viewer_ids": [],
  "editor_ids": []
}
```

`viewer_ids` / `editor_ids` default to `[]`. Mode fields default to
`everyone` / `owner`.

### `PUT /playlists/{id}` — split by caller role

Any user with **edit access** can update `title` and `description`.

Only the **owner** can update `view_mode`, `edit_mode`, `viewer_ids`, and
`editor_ids`. If a non-owner includes permission fields in the body, those
fields are silently ignored (not a 403 — the rest of the update still applies).

This keeps the update endpoint unified while clearly separating concerns.

### `DELETE /playlists/{id}` — owner only (was auth-required-any)

Returns 403 if the current user is not the owner.

### Track mutation endpoints — now check edit access

`POST /playlists/{id}/tracks`, `DELETE /playlists/{id}/tracks/{track_id}`,
`PUT /playlists/{id}/tracks/reorder` — return 403 if current user lacks edit
access. Previously: any authenticated user could mutate any playlist.

## Permission Check Logic (backend helper)

```python
def can_view(user, playlist) -> bool:
    if playlist.view_mode == "everyone":
        return True
    if user.id == playlist.owner_id:
        return True
    if playlist.view_mode == "users" and user.id in playlist.viewer_ids:
        return True
    # edit access implies view access
    if can_edit(user, playlist):
        return True
    return False

def can_edit(user, playlist) -> bool:
    if user.id == playlist.owner_id:
        return True
    if playlist.edit_mode == "everyone":
        return True
    if playlist.edit_mode == "users" and user.id in playlist.editor_ids:
        return True
    return False
```

`viewer_ids` and `editor_ids` are resolved from the join tables at query time
(eager-loaded via SQLAlchemy relationship or a simple join).

## Web UI Changes

### `PlaylistsPage.jsx` — list view

No structural change needed. The backend now filters the list, so inaccessible
playlists simply don't appear. Auth is now required to view this page at all
(add a login gate if not already present).

### `PlaylistPage.jsx` — detail view

**Permissions panel** (owner-only, triggered by a gear icon ⚙ in the playlist
header alongside the existing edit/delete controls):

- Opens as an inline panel below the header (not a modal — keeps it lightweight).
- Two sections: **Who can view** and **Who can edit**.
- Each section: three radio buttons — "Only me", "Specific users", "Everyone".
- When "Specific users" is selected: a checkbox list of all users except the owner
  (fetched from `GET /users`). Checks are the current `viewer_ids`/`editor_ids`.
- **Save button** — fires `PUT /playlists/{id}` with the updated permission fields.
- Panel is hidden from non-owners (they never see the gear icon).

**Owner indicator**: show `"by {owner_name}"` in the playlist subtitle when the
viewing user is not the owner (already have `owner_id` in the response; resolve
name from the `GET /users` result or include `owner_name` in the playlist object).

### `PlaylistCreate` modal — permission defaults

New playlists inherit the defaults (`view=everyone`, `edit=owner`) without
exposing permission controls in the create modal — keep create simple. The owner
can adjust permissions after creation via the gear panel.

## Out of Scope

- Playlist sharing via link (covered in `track-share-links.md`)
- Transferring playlist ownership
- Expiry or time-limited access
- "Anyone with link" mode (app is household-only, auth always required)
- Android — playlist permissions will be respected via the API naturally; no
  dedicated Android UI for the permissions panel in this phase
