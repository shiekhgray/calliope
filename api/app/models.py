from datetime import datetime

from sqlalchemy import (
    ARRAY, BigInteger, Boolean, Column, Date, DateTime, Float,
    ForeignKey, Integer, String, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)

    playlists = relationship("Playlist", back_populates="owner")


class Artist(Base):
    __tablename__ = "artists"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)

    albums = relationship("Album", back_populates="artist")


class Album(Base):
    __tablename__ = "albums"

    id = Column(Integer, primary_key=True)
    artist_id = Column(Integer, ForeignKey("artists.id"), nullable=False)
    title = Column(String(255), nullable=False)
    year = Column(Integer)
    cover_art_path = Column(Text)

    artist = relationship("Artist", back_populates="albums")
    tracks = relationship("Track", back_populates="album", order_by="Track.track_number")

    __table_args__ = (UniqueConstraint("artist_id", "title"),)


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=False)
    title = Column(String(255), nullable=False)
    track_number = Column(Integer)
    duration_ms = Column(Integer)
    bitrate_kbps = Column(Integer)
    file_path = Column(Text, unique=True, nullable=False)
    format = Column(String(8), nullable=False)
    play_count = Column(Integer, nullable=False, default=0)

    album = relationship("Album", back_populates="tracks")
    genres = relationship("Genre", secondary="track_genres", back_populates="tracks")
    playlist_entries = relationship("PlaylistTrack", back_populates="track")


class Genre(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), unique=True, nullable=False)

    tracks = relationship("Track", secondary="track_genres", back_populates="genres")


class TrackGenre(Base):
    __tablename__ = "track_genres"

    track_id = Column(Integer, ForeignKey("tracks.id"), primary_key=True)
    genre_id = Column(Integer, ForeignKey("genres.id"), primary_key=True)


class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="playlists")
    entries = relationship(
        "PlaylistTrack", back_populates="playlist",
        order_by="PlaylistTrack.position", cascade="all, delete-orphan"
    )


class Discovery(Base):
    __tablename__ = "discoveries"

    id = Column(Integer, primary_key=True)
    artist_id = Column(Integer, ForeignKey("artists.id", ondelete="CASCADE"), nullable=False)
    itunes_collection_id = Column(BigInteger, unique=True, nullable=False)
    album_title = Column(String(255), nullable=False)
    release_date = Column(Date)
    artwork_url = Column(Text)
    dismissed = Column(Boolean, nullable=False, default=False)
    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    artist = relationship("Artist")


class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    entity_type = Column(String(10), nullable=False)
    entity_id = Column(Integer, nullable=False)
    visited_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "entity_type", "entity_id"),)


class TrackVector(Base):
    __tablename__ = "track_vectors"

    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True)
    feature_vector = Column(Vector(38), nullable=False)
    file_mtime = Column(BigInteger, nullable=False)

    track = relationship("Track")


class VectorNormParams(Base):
    __tablename__ = "vector_norm_params"

    id = Column(Integer, primary_key=True)
    means = Column(ARRAY(Float), nullable=False)
    stds = Column(ARRAY(Float), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    id = Column(Integer, primary_key=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id"), nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    position = Column(Integer, nullable=False)

    playlist = relationship("Playlist", back_populates="entries")
    track = relationship("Track", back_populates="playlist_entries")
