"""add track_vectors_ki (key-invariant similarity space)

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-17

Parallel, derived table for the key-invariant chroma experiment. Mirrors
track_vectors (vector(60)) but stores chroma rotated to each track's detected
tonic. Fully regenerable from track_vectors via scripts/build_ki_vectors.py, so
this migration only creates empty structure. The KI z-score stats live in
vector_norm_params as the row with id=2 (no schema change; written by the builder).
"""
from alembic import op

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE TABLE track_vectors_ki ("
        "  track_id INTEGER PRIMARY KEY REFERENCES tracks(id) ON DELETE CASCADE,"
        "  feature_vector vector(60) NOT NULL,"
        "  file_mtime BIGINT NOT NULL"
        ")"
    )
    op.execute(
        "CREATE INDEX track_vectors_ki_hnsw_idx ON track_vectors_ki "
        "USING hnsw (feature_vector vector_cosine_ops)"
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS track_vectors_ki")
    op.execute("DELETE FROM vector_norm_params WHERE id = 2")
