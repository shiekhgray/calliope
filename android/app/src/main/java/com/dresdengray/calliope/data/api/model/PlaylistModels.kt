package com.dresdengray.calliope.data.api.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class Playlist(
    val id: Int,
    val title: String,
    val description: String?,
    @Json(name = "owner_id") val ownerId: Int,
    @Json(name = "created_at") val createdAt: String
)

@JsonClass(generateAdapter = true)
data class PlaylistEntry(
    val id: Int,
    val position: Int,
    val track: Track
)

@JsonClass(generateAdapter = true)
data class PlaylistDetail(
    val id: Int,
    val title: String,
    val description: String?,
    @Json(name = "owner_id") val ownerId: Int,
    @Json(name = "created_at") val createdAt: String,
    val entries: List<PlaylistEntry>
)

@JsonClass(generateAdapter = true)
data class CreatePlaylistRequest(
    val title: String,
    val description: String? = null
)

@JsonClass(generateAdapter = true)
data class AddTrackRequest(
    @Json(name = "track_id") val trackId: Int
)

@JsonClass(generateAdapter = true)
data class ReorderRequest(
    @Json(name = "track_ids") val trackIds: List<Int>
)
