"""add album_artists and track_credits tables; drop track_artist columns

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'album_artists',
        sa.Column('album_id', sa.Integer(), sa.ForeignKey('albums.id', ondelete='CASCADE'), nullable=False),
        sa.Column('artist_id', sa.Integer(), sa.ForeignKey('artists.id', ondelete='CASCADE'), nullable=False),
        sa.PrimaryKeyConstraint('album_id', 'artist_id'),
    )

    op.create_table(
        'track_credits',
        sa.Column('track_id', sa.Integer(), sa.ForeignKey('tracks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('artist_id', sa.Integer(), sa.ForeignKey('artists.id', ondelete='CASCADE'), nullable=False),
        sa.PrimaryKeyConstraint('track_id', 'artist_id'),
    )

    # Backfill: every existing album claims its current artist as a primary credit
    op.execute(
        "INSERT INTO album_artists (album_id, artist_id) SELECT id, artist_id FROM albums"
    )

    # Backfill: existing compilation track credits
    op.execute(
        "INSERT INTO track_credits (track_id, artist_id) "
        "SELECT id, track_artist_id FROM tracks WHERE track_artist_id IS NOT NULL"
    )

    op.drop_column('tracks', 'track_artist')
    op.drop_column('tracks', 'track_artist_id')


def downgrade():
    op.add_column('tracks', sa.Column('track_artist_id', sa.Integer(), sa.ForeignKey('artists.id'), nullable=True))
    op.add_column('tracks', sa.Column('track_artist', sa.String(255), nullable=True))

    # Restore track_artist_id from track_credits (best-effort: one row per track)
    op.execute(
        "UPDATE tracks t "
        "SET track_artist_id = tc.artist_id "
        "FROM track_credits tc "
        "WHERE tc.track_id = t.id"
    )

    # Restore track_artist name from artists table
    op.execute(
        "UPDATE tracks t "
        "SET track_artist = a.name "
        "FROM artists a "
        "WHERE t.track_artist_id = a.id"
    )

    op.drop_table('track_credits')
    op.drop_table('album_artists')
