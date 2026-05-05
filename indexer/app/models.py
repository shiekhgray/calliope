from datetime import datetime

from sqlalchemy import ARRAY, BigInteger, Column, DateTime, Float, Integer
from pgvector.sqlalchemy import Vector

from .database import Base


class TrackVector(Base):
    __tablename__ = "track_vectors"

    track_id = Column(Integer, primary_key=True)
    feature_vector = Column(Vector(60), nullable=False)
    file_mtime = Column(BigInteger, nullable=False)


class VectorNormParams(Base):
    __tablename__ = "vector_norm_params"

    id = Column(Integer, primary_key=True)
    means = Column(ARRAY(Float), nullable=False)
    stds = Column(ARRAY(Float), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
