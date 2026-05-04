"""expand feature_vector from 38 to 60 dimensions

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-04
"""
from alembic import op

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP INDEX IF EXISTS track_vectors_hnsw_idx")
    op.execute("TRUNCATE track_vectors")
    op.execute("DELETE FROM vector_norm_params")
    op.execute(
        "ALTER TABLE track_vectors "
        "ALTER COLUMN feature_vector TYPE vector(60) USING NULL"
    )
    op.execute(
        "CREATE INDEX track_vectors_hnsw_idx ON track_vectors "
        "USING hnsw (feature_vector vector_cosine_ops)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS track_vectors_hnsw_idx")
    op.execute("TRUNCATE track_vectors")
    op.execute("DELETE FROM vector_norm_params")
    op.execute(
        "ALTER TABLE track_vectors "
        "ALTER COLUMN feature_vector TYPE vector(38) USING NULL"
    )
    op.execute(
        "CREATE INDEX track_vectors_hnsw_idx ON track_vectors "
        "USING hnsw (feature_vector vector_cosine_ops)"
    )
