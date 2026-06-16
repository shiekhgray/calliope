"""add radio settings to users

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('radio_mode',    sa.String(16), nullable=False, server_default='classic'))
    op.add_column('users', sa.Column('radio_variety', sa.Integer(),  nullable=False, server_default='0'))


def downgrade():
    op.drop_column('users', 'radio_variety')
    op.drop_column('users', 'radio_mode')
