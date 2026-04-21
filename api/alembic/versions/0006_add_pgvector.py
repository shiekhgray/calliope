"""add pgvector extension and track_vectors / vector_norm_params tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("""
        CREATE TABLE track_vectors (
            track_id   INTEGER PRIMARY KEY REFERENCES tracks(id) ON DELETE CASCADE,
            feature_vector vector(38) NOT NULL,
            file_mtime BIGINT NOT NULL
        )
    """)

    op.execute("""
        CREATE INDEX track_vectors_hnsw_idx
        ON track_vectors USING hnsw (feature_vector vector_cosine_ops)
    """)

    op.create_table(
        'vector_norm_params',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('means', sa.ARRAY(sa.Float()), nullable=False),
        sa.Column('stds',  sa.ARRAY(sa.Float()), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('vector_norm_params')
    op.execute("DROP INDEX IF EXISTS track_vectors_hnsw_idx")
    op.execute("DROP TABLE IF EXISTS track_vectors")
    op.execute("DROP EXTENSION IF EXISTS vector")
