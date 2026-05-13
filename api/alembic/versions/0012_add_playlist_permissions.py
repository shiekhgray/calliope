"""add playlist permissions

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('playlists', sa.Column('view_mode', sa.String(10), nullable=False, server_default='everyone'))
    op.add_column('playlists', sa.Column('edit_mode', sa.String(10), nullable=False, server_default='owner'))

    op.create_table(
        'playlist_viewers',
        sa.Column('playlist_id', sa.Integer(), sa.ForeignKey('playlists.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    )

    op.create_table(
        'playlist_editors',
        sa.Column('playlist_id', sa.Integer(), sa.ForeignKey('playlists.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    )


def downgrade():
    op.drop_table('playlist_editors')
    op.drop_table('playlist_viewers')
    op.drop_column('playlists', 'edit_mode')
    op.drop_column('playlists', 'view_mode')
