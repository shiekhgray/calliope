"""PANNs CNN14 audio embeddings → track_vectors_embed (the default similarity space).

A pretrained 2048-dim audio embedding captures genre/instrumentation/vocal character
holistically — it decisively beat the hand-crafted 60-dim vector in owner A/B (see
prd/vector-tuning.md). CPU-only (~2.5s/track on the i7-10700K).

Imports torch/panns lazily and stubs matplotlib (panns_inference imports pyplot only
for unused plotting), so importing this module is cheap and the HTTP server startup
is unaffected — mirrors how index.py keeps librosa out of the hot path.
"""
import os
import sys

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

MUSIC_ROOT = os.environ.get("MUSIC_ROOT", "/music")
SR = 32000
BATCH = 50


def _load_model():
    import types
    mpl = types.ModuleType("matplotlib")
    mpl.pyplot = types.ModuleType("matplotlib.pyplot")
    sys.modules.setdefault("matplotlib", mpl)
    sys.modules.setdefault("matplotlib.pyplot", mpl.pyplot)
    import torch
    from panns_inference import AudioTagging
    torch.set_num_threads(max(1, (os.cpu_count() or 4)))
    return AudioTagging(checkpoint_path=None, device="cpu")


def build_embeddings(db: Session, update_status=None):
    """Embed every track whose track_vectors_embed row is missing or stale (mtime
    mismatch). Incremental + idempotent — safe to call at the end of each index run.
    """
    import librosa

    rows = db.execute(text("""
        SELECT t.id, t.file_path, e.file_mtime AS stored_mtime
        FROM tracks t
        LEFT JOIN track_vectors_embed e ON e.track_id = t.id
    """)).fetchall()

    todo = []
    for r in rows:
        fp = os.path.join(MUSIC_ROOT, r.file_path)
        if os.path.exists(fp):
            mtime = int(os.path.getmtime(fp))
            if r.stored_mtime is None or r.stored_mtime != mtime:
                todo.append((r.id, fp, mtime))

    if not todo:
        print("Embeddings: up to date.", flush=True)
        return

    print(f"Embeddings: {len(todo)} tracks to embed", flush=True)
    model = _load_model()
    ok = fail = 0
    batch = []

    def flush():
        if batch:
            db.execute(
                text("INSERT INTO track_vectors_embed (track_id, embedding, file_mtime) "
                     "VALUES (:tid, :emb, :mt) ON CONFLICT (track_id) DO UPDATE "
                     "SET embedding = EXCLUDED.embedding, file_mtime = EXCLUDED.file_mtime"),
                batch,
            )
            db.commit()

    for i, (tid, fp, mtime) in enumerate(todo, 1):
        try:
            y, _ = librosa.load(fp, sr=SR, mono=True)
            _, emb = model.inference(y[None, :])
            batch.append({"tid": tid, "emb": str(emb[0].tolist()), "mt": mtime})
            ok += 1
        except Exception as e:
            fail += 1
            print(f"Embeddings: error on {os.path.basename(fp)}: {e}", file=sys.stderr, flush=True)
        if len(batch) >= BATCH:
            flush(); batch = []
            if update_status:
                update_status(indexed=i)
    flush()
    print(f"Embeddings: done (ok={ok} fail={fail})", flush=True)


if __name__ == "__main__":
    # Manual full/incremental rebuild:  docker compose exec indexer python -m app.embeddings
    from .database import engine  # reuse the configured engine
    with Session(engine) as _db:
        build_embeddings(_db)
