package com.dresdengray.calliope.data.api.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class SearchResults(
    val artists: List<Artist> = emptyList(),
    val albums: List<Album> = emptyList(),
    val tracks: List<Track> = emptyList()
)

/**
 * History entry shape varies by entity_type, so most fields are nullable.
 * - artist: name only
 * - album:  name (album title) + artist info
 * - track:  name (track title) + album_id, album_title, artist_name (no artist_id from API)
 */
@JsonClass(generateAdapter = true)
data class SearchHistoryEntry(
    @Json(name = "entity_type") val entityType: String,
    @Json(name = "entity_id") val entityId: Int,
    val name: String,
    @Json(name = "album_id") val albumId: Int? = null,
    @Json(name = "album_title") val albumTitle: String? = null,
    @Json(name = "artist_id") val artistId: Int? = null,
    @Json(name = "artist_name") val artistName: String? = null
)

@JsonClass(generateAdapter = true)
data class SearchHistoryRequest(
    @Json(name = "entity_type") val entityType: String,
    @Json(name = "entity_id") val entityId: Int
)
