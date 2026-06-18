"""add track_vectors_embed (pretrained PANNs CNN14 audio embedding space)

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-17

Third similarity space (Vector Tuning experiment): a 2048-dim PANNs CNN14 audio
embedding per track, populated by indexer/build_embeddings.py. Unlike the 60-dim
DSP spaces this has no weight-groups — similarity is plain L2-normalized cosine
(no per-user sim_weight_* slicing). No ANN index (pgvector HNSW caps at 2000 dims;
the query is brute-force numpy anyway).
"""
from alembic import op

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE TABLE track_vectors_embed ("
        "  track_id INTEGER PRIMARY KEY REFERENCES tracks(id) ON DELETE CASCADE,"
        "  embedding vector(2048) NOT NULL,"
        "  file_mtime BIGINT NOT NULL"
        ")"
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS track_vectors_embed")
