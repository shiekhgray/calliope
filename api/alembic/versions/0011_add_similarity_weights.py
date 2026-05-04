"""add similarity weights to users

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('sim_weight_timbre',            sa.Integer(), nullable=False, server_default='5'))
    op.add_column('users', sa.Column('sim_weight_timbral_variation', sa.Integer(), nullable=False, server_default='5'))
    op.add_column('users', sa.Column('sim_weight_harmony',           sa.Integer(), nullable=False, server_default='5'))
    op.add_column('users', sa.Column('sim_weight_chord_movement',    sa.Integer(), nullable=False, server_default='5'))
    op.add_column('users', sa.Column('sim_weight_tempo',             sa.Integer(), nullable=False, server_default='5'))
    op.add_column('users', sa.Column('sim_weight_loudness',          sa.Integer(), nullable=False, server_default='5'))
    op.add_column('users', sa.Column('sim_weight_dynamic_range',     sa.Integer(), nullable=False, server_default='5'))
    op.add_column('users', sa.Column('sim_weight_brightness',        sa.Integer(), nullable=False, server_default='5'))
    op.add_column('users', sa.Column('sim_weight_tonal',             sa.Integer(), nullable=False, server_default='5'))


def downgrade():
    op.drop_column('users', 'sim_weight_tonal')
    op.drop_column('users', 'sim_weight_brightness')
    op.drop_column('users', 'sim_weight_dynamic_range')
    op.drop_column('users', 'sim_weight_loudness')
    op.drop_column('users', 'sim_weight_tempo')
    op.drop_column('users', 'sim_weight_chord_movement')
    op.drop_column('users', 'sim_weight_harmony')
    op.drop_column('users', 'sim_weight_timbral_variation')
    op.drop_column('users', 'sim_weight_timbre')
