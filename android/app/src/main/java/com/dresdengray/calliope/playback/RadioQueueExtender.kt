package com.dresdengray.calliope.playback

import androidx.media3.common.MediaItem
import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.api.model.Track
import com.dresdengray.calliope.data.db.DownloadedTrackDao
import java.io.File
import javax.inject.Inject

/**
 * Shared radio-mode logic: given a seed track, fetch similar tracks and turn them into
 * playable queue items. Extracted from PlayerViewModel.checkAndExtendRadioQueue so both
 * the phone player (PlayerViewModel) and Android Auto (MusicService) extend queues the
 * same way. Unscoped — Hilt creates a fresh instance wherever injected.
 */
class RadioQueueExtender @Inject constructor(
    private val api: CalliopeApi,
    private val downloadedTrackDao: DownloadedTrackDao,
) {

    /**
     * Similar tracks to [seedTrackId], dropping any whose id is in [excludeIds] (already
     * played / already queued this session), capped at [max]. Returns empty on API failure.
     */
    suspend fun nextTracks(seedTrackId: Int, excludeIds: Set<Int>, max: Int = 5): List<Track> {
        val similar = runCatching { api.getSimilarTracks(seedTrackId, limit = 10) }
            .getOrDefault(emptyList())
        return similar.filter { it.id !in excludeIds }.take(max)
    }

    /** Build a playable MediaItem, substituting a downloaded local file when present. */
    suspend fun toMediaItem(track: Track): MediaItem {
        val local = downloadedTrackDao.findDoneByTrackId(track.id.toLong())
        val localPath = local?.filePath?.takeIf { File(it).exists() }
        return track.toMediaItem(localFilePath = localPath)
    }
}
