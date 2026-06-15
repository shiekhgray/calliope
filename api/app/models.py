from datetime import datetime

from sqlalchemy import (
    ARRAY, BigInteger, Boolean, Column, Date, DateTime, Float,
    ForeignKey, Integer, String, Table, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.database import Base


# Association tables for playlist ACLs
playlist_viewers = Table(
    "playlist_viewers",
    Base.metadata,
    Column("playlist_id", Integer, ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

playlist_editors = Table(
    "playlist_editors",
    Base.metadata,
    Column("playlist_id", Integer, ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)

    sim_weight_timbre            = Column(Integer, nullable=False, default=5)
    sim_weight_timbral_variation = Column(Integer, nullable=False, default=5)
    sim_weight_harmony           = Column(Integer, nullable=False, default=5)
    sim_weight_chord_movement    = Column(Integer, nullable=False, default=5)
    sim_weight_tempo             = Column(Integer, nullable=False, default=5)
    sim_weight_loudness          = Column(Integer, nullable=False, default=5)
    sim_weight_dynamic_range     = Column(Integer, nullable=False, default=5)
    sim_weight_brightness        = Column(Integer, nullable=False, default=5)
    sim_weight_tonal             = Column(Integer, nullable=False, default=5)

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
    album_type = Column(String(8), nullable=False, default="album")

    artist = relationship("Artist", back_populates="albums")
    tracks = relationship("Track", back_populates="album", order_by="Track.track_number")

    __table_args__ = (UniqueConstraint("artist_id", "title"),)


class AlbumArtist(Base):
    __tablename__ = "album_artists"

    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), primary_key=True)
    artist_id = Column(Integer, ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True)


class TrackCredit(Base):
    __tablename__ = "track_credits"

    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True)
    artist_id = Column(Integer, ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True)


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
    view_mode = Column(String(10), nullable=False, default="everyone")
    edit_mode = Column(String(10), nullable=False, default="owner")

    owner = relationship("User", back_populates="playlists")
    entries = relationship(
        "PlaylistTrack", back_populates="playlist",
        order_by="PlaylistTrack.position", cascade="all, delete-orphan"
    )
    viewers = relationship("User", secondary="playlist_viewers", lazy="select")
    editors = relationship("User", secondary="playlist_editors", lazy="select")


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
    feature_vector = Column(Vector(60), nullable=False)
    file_mtime = Column(BigInteger, nullable=False)

    track = relationship("Track")


class VectorNormParams(Base):
    __tablename__ = "vector_norm_params"

    id = Column(Integer, primary_key=True)
    means = Column(ARRAY(Float), nullable=False)
    stds = Column(ARRAY(Float), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TrackMapCoords(Base):
    __tablename__ = "track_map_coords"

    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    cluster_id = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    track = relationship("Track")


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    id = Column(Integer, primary_key=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id"), nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    position = Column(Integer, nullable=False)

    playlist = relationship("Playlist", back_populates="entries")
    track = relationship("Track", back_populates="playlist_entries")
