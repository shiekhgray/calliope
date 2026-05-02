package com.dresdengray.calliope.data.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface DownloadedTrackDao {

    @Query("SELECT * FROM downloaded_tracks WHERE playlist_id = :playlistId")
    fun observeByPlaylist(playlistId: Long): Flow<List<DownloadedTrack>>

    /** Returns the first DONE entry for a given track across any playlist. */
    @Query("SELECT * FROM downloaded_tracks WHERE track_id = :trackId AND status = 'DONE' LIMIT 1")
    suspend fun findDoneByTrackId(trackId: Long): DownloadedTrack?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(track: DownloadedTrack)

    @Query("DELETE FROM downloaded_tracks WHERE playlist_id = :playlistId")
    suspend fun deleteByPlaylist(playlistId: Long)

    @Query("UPDATE downloaded_tracks SET status = :status WHERE playlist_id = :playlistId AND track_id = :trackId")
    suspend fun updateStatus(playlistId: Long, trackId: Long, status: DownloadStatus)
}
