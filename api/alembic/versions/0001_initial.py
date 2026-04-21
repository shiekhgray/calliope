"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-13
"""

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(128), nullable=False),
    )

    op.create_table(
        "artists",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
    )

    op.create_table(
        "albums",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("artist_id", sa.Integer, sa.ForeignKey("artists.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("year", sa.Integer),
        sa.Column("cover_art_path", sa.Text),
        sa.UniqueConstraint("artist_id", "title"),
    )

    op.create_table(
        "tracks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("album_id", sa.Integer, sa.ForeignKey("albums.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("track_number", sa.Integer),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("file_path", sa.Text, nullable=False, unique=True),
        sa.Column("format", sa.String(8), nullable=False),
    )

    op.create_table(
        "genres",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
    )

    op.create_table(
        "track_genres",
        sa.Column("track_id", sa.Integer, sa.ForeignKey("tracks.id"), primary_key=True),
        sa.Column("genre_id", sa.Integer, sa.ForeignKey("genres.id"), primary_key=True),
    )

    op.create_table(
        "playlists",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "playlist_tracks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("playlist_id", sa.Integer, sa.ForeignKey("playlists.id"), nullable=False),
        sa.Column("track_id", sa.Integer, sa.ForeignKey("tracks.id"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
    )

    # Indexes for common access patterns
    op.create_index("ix_albums_artist_id", "albums", ["artist_id"])
    op.create_index("ix_tracks_album_id", "tracks", ["album_id"])
    op.create_index("ix_playlist_tracks_playlist_id", "playlist_tracks", ["playlist_id"])


def downgrade():
    op.drop_table("playlist_tracks")
    op.drop_table("playlists")
    op.drop_table("track_genres")
    op.drop_table("genres")
    op.drop_table("tracks")
    op.drop_table("albums")
    op.drop_table("artists")
    op.drop_table("users")
