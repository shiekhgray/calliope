package com.dresdengray.calliope.work

import android.content.Context
import android.content.pm.ServiceInfo
import androidx.core.app.NotificationCompat
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.OneTimeWorkRequest
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.dresdengray.calliope.App
import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.db.DownloadStatus
import com.dresdengray.calliope.data.db.DownloadedTrack
import com.dresdengray.calliope.data.db.DownloadedTrackDao
import com.dresdengray.calliope.util.Constants
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File

@HiltWorker
class DownloadPlaylistWorker @AssistedInject constructor(
    @Assisted private val appContext: Context,
    @Assisted params: WorkerParameters,
    private val api: CalliopeApi,
    private val dao: DownloadedTrackDao,
    private val okHttpClient: OkHttpClient
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val playlistId = inputData.getLong(KEY_PLAYLIST_ID, -1L)
        if (playlistId == -1L) return Result.failure()

        setForeground(buildForegroundInfo(playlistId, 0, 0))

        val playlist = try {
            api.getPlaylist(playlistId.toInt())
        } catch (e: Exception) {
            return Result.retry()
        }

        val tracks = playlist.entries.sortedBy { it.position }.map { it.track }
        val total = tracks.size
        var done = 0

        for (track in tracks) {
            if (isStopped) return Result.failure()

            val existing = dao.findDoneByTrackId(track.id.toLong())
            if (existing != null) {
                done++
                setForeground(buildForegroundInfo(playlistId, done, total))
                continue
            }

            val ext = track.format?.lowercase() ?: "mp3"
            val dir = File(appContext.filesDir, "playlists/$playlistId")
            dir.mkdirs()
            val destFile = File(dir, "${track.id}.$ext")

            dao.upsert(DownloadedTrack(
                playlistId = playlistId,
                trackId = track.id.toLong(),
                filePath = destFile.absolutePath,
                downloadedAt = 0L,
                status = DownloadStatus.DOWNLOADING
            ))

            val success = downloadFile(track.id, destFile)
            if (success) {
                dao.upsert(DownloadedTrack(
                    playlistId = playlistId,
                    trackId = track.id.toLong(),
                    filePath = destFile.absolutePath,
                    downloadedAt = System.currentTimeMillis(),
                    status = DownloadStatus.DONE
                ))
                done++
            } else {
                dao.updateStatus(playlistId, track.id.toLong(), DownloadStatus.FAILED)
                destFile.delete()
            }

            setForeground(buildForegroundInfo(playlistId, done, total))
        }

        return Result.success()
    }

    // OkHttpClient already carries the AuthInterceptor which adds the Bearer token.
    private suspend fun downloadFile(trackId: Int, destFile: File): Boolean =
        withContext(Dispatchers.IO) {
            try {
                val request = Request.Builder()
                    .url(Constants.streamUrl(trackId))
                    .build()
                okHttpClient.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return@withContext false
                    val body = response.body ?: return@withContext false
                    destFile.outputStream().use { body.byteStream().copyTo(it) }
                    true
                }
            } catch (e: Exception) {
                destFile.delete()
                false
            }
        }

    private fun buildForegroundInfo(playlistId: Long, done: Int, total: Int): ForegroundInfo {
        val notification = NotificationCompat.Builder(appContext, App.DOWNLOAD_CHANNEL_ID)
            .setContentTitle("Downloading playlist")
            .setContentText(if (total > 0) "$done / $total tracks" else "Preparing…")
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setProgress(total, done, total == 0)
            .setOngoing(true)
            .setSilent(true)
            .build()

        // 3-arg ForegroundInfo required on API 34+ for type enforcement.
        // FOREGROUND_SERVICE_TYPE_DATA_SYNC is an inlined int constant — safe on all API levels.
        return ForegroundInfo(
            playlistId.toInt(),
            notification,
            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
        )
    }

    companion object {
        const val KEY_PLAYLIST_ID = "playlist_id"
        const val TAG_PREFIX = "playlist_"

        fun buildRequest(playlistId: Long): OneTimeWorkRequest =
            OneTimeWorkRequestBuilder<DownloadPlaylistWorker>()
                .setInputData(workDataOf(KEY_PLAYLIST_ID to playlistId))
                .addTag("$TAG_PREFIX$playlistId")
                .build()
    }
}
