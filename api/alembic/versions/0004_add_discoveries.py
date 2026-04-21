"""add discoveries table

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-14
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'discoveries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('artist_id', sa.Integer(), sa.ForeignKey('artists.id', ondelete='CASCADE'), nullable=False),
        sa.Column('itunes_collection_id', sa.BigInteger(), nullable=False),
        sa.Column('album_title', sa.String(255), nullable=False),
        sa.Column('release_date', sa.Date(), nullable=True),
        sa.Column('artwork_url', sa.Text(), nullable=True),
        sa.Column('dismissed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('first_seen_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('itunes_collection_id'),
    )
    op.create_index('ix_discoveries_artist_id', 'discoveries', ['artist_id'])


def downgrade():
    op.drop_index('ix_discoveries_artist_id', 'discoveries')
    op.drop_table('discoveries')
