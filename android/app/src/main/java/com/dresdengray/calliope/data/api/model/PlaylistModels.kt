package com.dresdengray.calliope.data.api.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class Playlist(
    val id: Int,
    val title: String,
    val description: String?,
    @Json(name = "owner_id") val ownerId: Int,
    @Json(name = "created_at") val createdAt: String,
    // Permission fields added in API migration 0012
    @Json(name = "view_mode") val viewMode: String = "everyone",
    @Json(name = "edit_mode") val editMode: String = "owner",
    @Json(name = "viewer_ids") val viewerIds: List<Int> = emptyList(),
    @Json(name = "editor_ids") val editorIds: List<Int> = emptyList()
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
    val entries: List<PlaylistEntry>,
    @Json(name = "view_mode") val viewMode: String = "everyone",
    @Json(name = "edit_mode") val editMode: String = "owner",
    @Json(name = "viewer_ids") val viewerIds: List<Int> = emptyList(),
    @Json(name = "editor_ids") val editorIds: List<Int> = emptyList()
)

@JsonClass(generateAdapter = true)
data class CreatePlaylistRequest(
    val title: String,
    val description: String? = null,
    @Json(name = "view_mode") val viewMode: String = "everyone",
    @Json(name = "edit_mode") val editMode: String = "owner"
)

@JsonClass(generateAdapter = true)
data class AddTrackRequest(
    @Json(name = "track_id") val trackId: Int
)

@JsonClass(generateAdapter = true)
data class ReorderRequest(
    @Json(name = "track_ids") val trackIds: List<Int>
)
