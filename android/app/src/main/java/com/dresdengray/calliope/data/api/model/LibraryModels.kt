package com.dresdengray.calliope.data.api.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class Artist(val id: Int, val name: String)

@JsonClass(generateAdapter = true)
data class Album(
    val id: Int,
    val title: String,
    val year: Int?,
    @Json(name = "cover_art_path") val coverArtPath: String?,
    @Json(name = "artist_id") val artistId: Int,
    @Json(name = "artist_name") val artistName: String,
    // "album", "ep", or "single"
    @Json(name = "album_type") val albumType: String = "album"
)

@JsonClass(generateAdapter = true)
data class Track(
    val id: Int,
    val title: String,
    @Json(name = "track_number") val trackNumber: Int?,
    @Json(name = "duration_ms") val durationMs: Long?,
    @Json(name = "bitrate_kbps") val bitrateKbps: Int?,
    val format: String?,
    @Json(name = "play_count") val playCount: Int = 0,
    // Populated by the API on search/playlist/top-track endpoints;
    // enriched from album context on album-detail tracks (see AlbumViewModel)
    @Json(name = "album_id") val albumId: Int = 0,
    @Json(name = "album_title") val albumTitle: String = "",
    @Json(name = "artist_id") val artistId: Int = 0,
    @Json(name = "artist_name") val artistName: String = ""
)

@JsonClass(generateAdapter = true)
data class PlayedResponse(@Json(name = "play_count") val playCount: Int)

@JsonClass(generateAdapter = true)
data class AlbumDetail(
    val id: Int,
    val title: String,
    val year: Int?,
    @Json(name = "cover_art_path") val coverArtPath: String?,
    @Json(name = "artist_id") val artistId: Int,
    @Json(name = "artist_name") val artistName: String,
    @Json(name = "album_type") val albumType: String = "album",
    val tracks: List<Track>
)
