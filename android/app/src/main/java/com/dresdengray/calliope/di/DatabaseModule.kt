package com.dresdengray.calliope.di

import android.content.Context
import androidx.room.Room
import androidx.work.WorkManager
import com.dresdengray.calliope.data.db.CalliopeDatabase
import com.dresdengray.calliope.data.db.DownloadedTrackDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides @Singleton
    fun provideDatabase(@ApplicationContext context: Context): CalliopeDatabase =
        Room.databaseBuilder(context, CalliopeDatabase::class.java, "calliope.db")
            .fallbackToDestructiveMigration()
            .build()

    @Provides
    fun provideDownloadedTrackDao(db: CalliopeDatabase): DownloadedTrackDao =
        db.downloadedTrackDao()

    @Provides @Singleton
    fun provideWorkManager(@ApplicationContext context: Context): WorkManager =
        WorkManager.getInstance(context)
}
