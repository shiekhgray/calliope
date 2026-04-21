"""add bitrate_kbps to tracks

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-13
"""

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column("tracks", sa.Column("bitrate_kbps", sa.Integer, nullable=True))


def downgrade():
    op.drop_column("tracks", "bitrate_kbps")
