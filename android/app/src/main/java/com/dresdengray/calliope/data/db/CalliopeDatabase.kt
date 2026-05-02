package com.dresdengray.calliope.data.db

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.TypeConverter
import androidx.room.TypeConverters

@Database(entities = [DownloadedTrack::class], version = 1, exportSchema = false)
@TypeConverters(DownloadStatusConverter::class)
abstract class CalliopeDatabase : RoomDatabase() {
    abstract fun downloadedTrackDao(): DownloadedTrackDao
}

class DownloadStatusConverter {
    @TypeConverter fun fromStatus(status: DownloadStatus): String = status.name
    @TypeConverter fun toStatus(value: String): DownloadStatus = DownloadStatus.valueOf(value)
}
