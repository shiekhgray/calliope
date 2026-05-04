"""add album_type column to albums

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'albums',
        sa.Column('album_type', sa.String(8), nullable=False, server_default='album'),
    )


def downgrade():
    op.drop_column('albums', 'album_type')
