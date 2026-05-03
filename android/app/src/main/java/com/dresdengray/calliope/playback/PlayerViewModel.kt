package com.dresdengray.calliope.playback

import android.content.ComponentName
import android.content.Context
import android.net.Uri
import android.os.Bundle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.api.model.Track
import com.dresdengray.calliope.data.db.DownloadedTrackDao
import com.dresdengray.calliope.util.Constants
import com.dresdengray.calliope.util.NetworkMonitor
import java.io.File
import com.google.common.util.concurrent.ListenableFuture
import com.google.common.util.concurrent.MoreExecutors
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import javax.inject.Inject

data class PlayerUiState(
    val currentTrack: Track? = null,
    val isPlaying: Boolean = false,
    val positionMs: Long = 0L,
    val durationMs: Long = 0L,
    val queueTracks: List<Track> = emptyList(),
    val currentIndex: Int = -1
)

@HiltViewModel
class PlayerViewModel @Inject constructor(
    @ApplicationContext private val context: Context,
    private val downloadedTrackDao: DownloadedTrackDao,
    private val networkMonitor: NetworkMonitor,
    private val api: CalliopeApi
) : ViewModel() {

    private val _uiState = MutableStateFlow(PlayerUiState())
    val uiState: StateFlow<PlayerUiState> = _uiState.asStateFlow()

    private val _similarTracks = MutableStateFlow<List<Track>>(emptyList())
    val similarTracks: StateFlow<List<Track>> = _similarTracks.asStateFlow()

    private val _radioMode = MutableStateFlow(false)
    val radioMode: StateFlow<Boolean> = _radioMode.asStateFlow()

    // WiFi guard — session-scoped, cleared when ViewModel is destroyed
    private var wifiGuardConfirmed = false
    private var pendingPlay: Pair<List<Track>, Int>? = null
    val showStreamingWifiWarning = MutableStateFlow(false)

    private var mediaController: MediaController? = null
    private var controllerFuture: ListenableFuture<MediaController>? = null
    private var positionJob: Job? = null
    private var similarTracksJob: Job? = null

    // Local mirror of the queue — needed to resolve Track from currentMediaItemIndex
    private val _queueTracks = mutableListOf<Track>()

    private val playerListener = object : Player.Listener {
        override fun onIsPlayingChanged(isPlaying: Boolean) {
            _uiState.update { it.copy(isPlaying = isPlaying) }
            if (isPlaying) startPositionUpdates() else stopPositionUpdates()
        }

        override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
            val index = mediaController?.currentMediaItemIndex ?: -1
            val track = _queueTracks.getOrNull(index)
                ?: mediaItem?.toTrack() // fallback: reconstruct from metadata
            val duration = mediaController?.duration?.takeIf { it > 0 } ?: 0L
            _uiState.update {
                it.copy(
                    currentTrack = track,
                    currentIndex = index,
                    positionMs = 0L,
                    durationMs = duration
                )
            }
            val trackId = track?.id ?: return
            fetchSimilarTracks(trackId)
            if (_radioMode.value) checkAndExtendRadioQueue(trackId)
        }

        override fun onPlaybackStateChanged(state: Int) {
            val duration = mediaController?.duration?.takeIf { it > 0 } ?: 0L
            _uiState.update { it.copy(durationMs = duration) }
        }
    }

    init {
        connectToService()
    }

    private fun connectToService() {
        val sessionToken = SessionToken(
            context,
            ComponentName(context, MusicService::class.java)
        )
        val future = MediaController.Builder(context, sessionToken).buildAsync()
        controllerFuture = future
        future.addListener({
            runCatching {
                val controller = future.get()
                mediaController = controller
                controller.addListener(playerListener)
                // Sync state in case service was already playing (e.g. app was killed and restarted)
                syncStateFromController(controller)
            }
        }, MoreExecutors.directExecutor())
    }

    private fun syncStateFromController(controller: MediaController) {
        val index = controller.currentMediaItemIndex
        val track = _queueTracks.getOrNull(index)
            ?: controller.currentMediaItem?.toTrack()
        val duration = controller.duration.takeIf { it > 0 } ?: 0L
        _uiState.update {
            it.copy(
                currentTrack = track,
                isPlaying = controller.isPlaying,
                positionMs = controller.currentPosition.coerceAtLeast(0L),
                durationMs = duration,
                currentIndex = index
            )
        }
        if (controller.isPlaying) startPositionUpdates()
        track?.let { fetchSimilarTracks(it.id) }
    }

    /** Play a list of tracks, starting at [startIndex]. Shows a WiFi warning if on cellular. */
    fun playQueue(tracks: List<Track>, startIndex: Int = 0) {
        if (networkMonitor.isOnWifi() || wifiGuardConfirmed) {
            executePlay(tracks, startIndex)
        } else {
            pendingPlay = tracks to startIndex
            showStreamingWifiWarning.value = true
        }
    }

    fun confirmStreamingOnCellular() {
        wifiGuardConfirmed = true
        showStreamingWifiWarning.value = false
        pendingPlay?.let { (tracks, index) -> executePlay(tracks, index) }
        pendingPlay = null
    }

    fun dismissStreamingWarning() {
        showStreamingWifiWarning.value = false
        pendingPlay = null
    }

    private fun executePlay(tracks: List<Track>, startIndex: Int) {
        _queueTracks.clear()
        _queueTracks.addAll(tracks)
        _uiState.update {
            it.copy(
                queueTracks = tracks.toList(),
                currentIndex = startIndex,
                currentTrack = tracks.getOrNull(startIndex)
            )
        }

        viewModelScope.launch {
            val items = tracks.map { track ->
                val local = downloadedTrackDao.findDoneByTrackId(track.id.toLong())
                val localPath = local?.filePath?.takeIf { File(it).exists() }
                track.toMediaItem(localFilePath = localPath)
            }
            mediaController?.run {
                setMediaItems(items, startIndex, 0L)
                prepare()
                play()
            }
        }
    }

    fun togglePlayPause() {
        mediaController?.let {
            if (it.isPlaying) it.pause() else it.play()
        }
    }

    fun skipToNext() {
        mediaController?.seekToNextMediaItem()
    }

    /**
     * If more than 3 s into the track, restart it. Otherwise go to previous.
     */
    fun skipToPrev() {
        val controller = mediaController ?: return
        if (controller.currentPosition > 3_000) {
            controller.seekTo(0)
        } else {
            controller.seekToPreviousMediaItem()
        }
    }

    fun seekTo(positionMs: Long) {
        mediaController?.seekTo(positionMs)
        _uiState.update { it.copy(positionMs = positionMs) }
    }

    fun toggleRadioMode() {
        val nowOn = !_radioMode.value
        _radioMode.value = nowOn
        if (nowOn) {
            _uiState.value.currentTrack?.let { checkAndExtendRadioQueue(it.id) }
        }
    }

    private fun fetchSimilarTracks(trackId: Int) {
        similarTracksJob?.cancel()
        similarTracksJob = viewModelScope.launch {
            _similarTracks.value = emptyList()
            runCatching { api.getSimilarTracks(trackId, limit = 5) }
                .onSuccess { _similarTracks.value = it }
        }
    }

    /** When radio mode is on and the queue is nearly empty, append similar tracks. */
    private fun checkAndExtendRadioQueue(currentTrackId: Int) {
        val controller = mediaController ?: return
        val remaining = controller.mediaItemCount - controller.currentMediaItemIndex - 1
        if (remaining > 1) return
        viewModelScope.launch {
            runCatching { api.getSimilarTracks(currentTrackId, limit = 10) }
                .onSuccess { similar ->
                    val existingIds = _queueTracks.map { it.id }.toSet()
                    val toAppend = similar.filter { it.id !in existingIds }.take(5)
                    if (toAppend.isEmpty()) return@onSuccess
                    val items = toAppend.map { track ->
                        val local = downloadedTrackDao.findDoneByTrackId(track.id.toLong())
                        val localPath = local?.filePath?.takeIf { File(it).exists() }
                        track.toMediaItem(localFilePath = localPath)
                    }
                    _queueTracks.addAll(toAppend)
                    _uiState.update { it.copy(queueTracks = _queueTracks.toList()) }
                    items.forEach { controller.addMediaItem(it) }
                }
        }
    }

    private fun startPositionUpdates() {
        positionJob?.cancel()
        positionJob = viewModelScope.launch {
            while (isActive) {
                val pos = mediaController?.currentPosition?.coerceAtLeast(0L) ?: 0L
                val dur = mediaController?.duration?.takeIf { it > 0 } ?: 0L
                _uiState.update { it.copy(positionMs = pos, durationMs = dur) }
                delay(500)
            }
        }
    }

    private fun stopPositionUpdates() {
        positionJob?.cancel()
        positionJob = null
        _uiState.update {
            it.copy(positionMs = mediaController?.currentPosition?.coerceAtLeast(0L) ?: 0L)
        }
    }

    override fun onCleared() {
        stopPositionUpdates()
        similarTracksJob?.cancel()
        mediaController?.removeListener(playerListener)
        controllerFuture?.let { MediaController.releaseFuture(it) }
        super.onCleared()
    }
}

// ---------------------------------------------------------------------------
// Extension helpers
// ---------------------------------------------------------------------------

private fun Track.toMediaItem(localFilePath: String? = null): MediaItem {
    val uri = if (localFilePath != null) Uri.fromFile(File(localFilePath))
              else Uri.parse(Constants.streamUrl(id))
    val extras = Bundle().apply {
        putInt("albumId", albumId)
        putInt("artistId", artistId)
        putString("albumTitle", albumTitle)
        putString("artistName", artistName)
    }
    return MediaItem.Builder()
        .setUri(uri)
        .setMediaId(id.toString())
        .setMediaMetadata(
            MediaMetadata.Builder()
                .setTitle(title)
                .setArtist(artistName)
                .setAlbumTitle(albumTitle)
                .setArtworkUri(Uri.parse(Constants.albumArtUrl(albumId)))
                .setExtras(extras)
                .build()
        )
        .build()
}

/** Reconstruct a lightweight Track from MediaItem metadata (used when ViewModel queue is lost). */
private fun MediaItem.toTrack(): Track {
    val meta = mediaMetadata
    val extras = meta.extras
    return Track(
        id = mediaId.toIntOrNull() ?: 0,
        title = meta.title?.toString() ?: "",
        trackNumber = null,
        durationMs = null,
        bitrateKbps = null,
        format = null,
        playCount = 0,
        albumId = extras?.getInt("albumId") ?: 0,
        albumTitle = extras?.getString("albumTitle") ?: "",
        artistId = extras?.getInt("artistId") ?: 0,
        artistName = extras?.getString("artistName") ?: meta.artist?.toString() ?: ""
    )
}
