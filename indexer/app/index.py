"""Feature extraction and vector indexing."""
import sys
from datetime import datetime
from pathlib import Path

import librosa
import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import MUSIC_ROOT
from .database import engine
from .models import TrackVector, VectorNormParams

# Load only the first 60s of each track — captures musical character, keeps extraction fast.
ANALYSIS_DURATION = 60


def extract_features(file_path: Path) -> np.ndarray:
    """Return a 60-dim feature vector.

    Dims  0–12: MFCC mean
    Dims 13–25: MFCC variance
    Dims 26–37: chroma mean
    Dims 38–49: chroma variance
    Dim  50:    tempo (BPM)
    Dim  51:    RMS mean
    Dim  52:    RMS variance
    Dim  53:    spectral centroid mean
    Dims 54–59: tonnetz mean
    """
    y, sr = librosa.load(str(file_path), sr=22050, mono=True, duration=ANALYSIS_DURATION)

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_mean = np.mean(mfcc, axis=1)       # 13  dims 0–12
    mfcc_var  = np.var(mfcc, axis=1)        # 13  dims 13–25

    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    chroma_mean = np.mean(chroma, axis=1)   # 12  dims 26–37
    chroma_var  = np.var(chroma, axis=1)    # 12  dims 38–49

    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    tempo_val = float(np.atleast_1d(tempo)[0])   # 1   dim 50

    rms = librosa.feature.rms(y=y)[0]
    rms_mean = np.mean(rms)                 # 1   dim 51
    rms_var  = np.var(rms)                  # 1   dim 52

    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    centroid_mean = np.mean(centroid)       # 1   dim 53

    y_harm = librosa.effects.harmonic(y)
    tonnetz = librosa.feature.tonnetz(y=y_harm, sr=sr)
    tonnetz_mean = np.mean(tonnetz, axis=1) # 6   dims 54–59

    return np.concatenate([
        mfcc_mean, mfcc_var,
        chroma_mean, chroma_var,
        [tempo_val], [rms_mean], [rms_var], [centroid_mean],
        tonnetz_mean,
    ]).astype(np.float32)


def run_indexing(update_status):
    """Index all stale or missing tracks, then recompute norm params."""
    music_root = Path(MUSIC_ROOT)

    with Session(engine) as db:
        rows = db.execute(text("""
            SELECT t.id, t.file_path, tv.file_mtime AS stored_mtime
            FROM tracks t
            LEFT JOIN track_vectors tv ON tv.track_id = t.id
        """)).fetchall()

        to_index = []
        for row in rows:
            fp = music_root / row.file_path
            if fp.exists():
                mtime = int(fp.stat().st_mtime)
                if row.stored_mtime is None or row.stored_mtime != mtime:
                    to_index.append((row.id, fp, mtime))

        update_status(to_index=len(to_index), indexed=0)
        print(f"Indexer: {len(to_index)} tracks to process", flush=True)

        for i, (track_id, fp, mtime) in enumerate(to_index):
            try:
                vec = extract_features(fp)
                tv = db.get(TrackVector, track_id)
                if tv:
                    tv.feature_vector = vec.tolist()
                    tv.file_mtime = mtime
                else:
                    db.add(TrackVector(
                        track_id=track_id,
                        feature_vector=vec.tolist(),
                        file_mtime=mtime,
                    ))
                db.commit()
            except Exception as e:
                print(f"Indexer: error on {fp.name}: {e}", file=sys.stderr, flush=True)
            update_status(indexed=i + 1)

        _recompute_norm_params(db)
        db.commit()

        # Keep the Music Map atlas current: place any new tracks into the frozen
        # UMAP embedding (cheap) and refresh default clusters.
        try:
            from .mapping import build_map
            build_map(db, full_refit=False)
        except Exception as e:
            print(f"Indexer: map build failed: {e}", file=sys.stderr, flush=True)

    print("Indexer: done", flush=True)


def _recompute_norm_params(db: Session):
    all_tv = db.query(TrackVector).all()
    if not all_tv:
        return
    matrix = np.array([v.feature_vector for v in all_tv], dtype=np.float64)
    means = np.mean(matrix, axis=0).tolist()
    stds  = np.std(matrix, axis=0).tolist()

    norm = db.get(VectorNormParams, 1)
    if norm:
        norm.means = means
        norm.stds  = stds
        norm.updated_at = datetime.utcnow()
    else:
        db.add(VectorNormParams(id=1, means=means, stds=stds, updated_at=datetime.utcnow()))
