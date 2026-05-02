package com.dresdengray.calliope.data.db

import androidx.room.ColumnInfo
import androidx.room.Entity

@Entity(
    tableName = "downloaded_tracks",
    primaryKeys = ["playlist_id", "track_id"]
)
data class DownloadedTrack(
    @ColumnInfo(name = "playlist_id") val playlistId: Long,
    @ColumnInfo(name = "track_id") val trackId: Long,
    @ColumnInfo(name = "file_path") val filePath: String,
    @ColumnInfo(name = "downloaded_at") val downloadedAt: Long,
    val status: DownloadStatus
)
