"""add search_history table

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-15
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'search_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('entity_type', sa.String(10), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('visited_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'entity_type', 'entity_id'),
    )
    op.create_index('ix_search_history_user', 'search_history', ['user_id', 'visited_at'])


def downgrade():
    op.drop_index('ix_search_history_user', 'search_history')
    op.drop_table('search_history')
