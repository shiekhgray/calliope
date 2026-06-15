"""add track_map_coords (music map atlas)

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'track_map_coords',
        sa.Column('track_id', sa.Integer(),
                  sa.ForeignKey('tracks.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('x', sa.Float(), nullable=False),
        sa.Column('y', sa.Float(), nullable=False),
        sa.Column('cluster_id', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('now()')),
    )


def downgrade():
    op.drop_table('track_map_coords')
