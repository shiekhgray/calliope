"""add play_count to tracks

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-14
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'tracks',
        sa.Column('play_count', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade():
    op.drop_column('tracks', 'play_count')
