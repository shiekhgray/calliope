package com.dresdengray.calliope.playback

import android.app.PendingIntent
import android.content.Intent
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.session.LibraryResult
import androidx.media3.session.MediaLibraryService
import androidx.media3.session.MediaSession
import com.dresdengray.calliope.MainActivity
import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.auth.TokenStorage
import com.google.common.collect.ImmutableList
import com.google.common.util.concurrent.Futures
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import javax.inject.Inject

@AndroidEntryPoint
class MusicService : MediaLibraryService() {

    @Inject lateinit var tokenStorage: TokenStorage
    @Inject lateinit var api: CalliopeApi

    private lateinit var player: ExoPlayer
    private lateinit var mediaSession: MediaLibrarySession

    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    // Play count tracking: report only on natural track completion
    private var currentTrackId: Int? = null
    private val reportedThisSession = mutableSetOf<Int>()

    private val playerListener = object : Player.Listener {
        override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
            if (reason == Player.MEDIA_ITEM_TRANSITION_REASON_AUTO) {
                // Previous track finished naturally — report it
                currentTrackId?.let { reportPlayCount(it) }
            }
            currentTrackId = mediaItem?.mediaId?.toIntOrNull()
        }

        override fun onPlaybackStateChanged(playbackState: Int) {
            if (playbackState == Player.STATE_ENDED) {
                // Last track in queue ended naturally
                currentTrackId?.let { reportPlayCount(it) }
            }
        }
    }

    private fun reportPlayCount(trackId: Int) {
        if (reportedThisSession.contains(trackId)) return
        reportedThisSession.add(trackId)
        serviceScope.launch {
            runCatching { api.reportPlayed(trackId) }
        }
    }

    // Android Auto browse root item
    private val rootItem = MediaItem.Builder()
        .setMediaId("root")
        .setMediaMetadata(
            MediaMetadata.Builder()
                .setIsBrowsable(true)
                .setIsPlayable(false)
                .setTitle("Calliope")
                .build()
        )
        .build()

    private val libraryCallback = object : MediaLibrarySession.Callback {
        override fun onGetLibraryRoot(
            session: MediaLibrarySession,
            browser: MediaSession.ControllerInfo,
            params: LibraryParams?
        ) = Futures.immediateFuture(LibraryResult.ofItem(rootItem, null))

        override fun onGetChildren(
            session: MediaLibrarySession,
            browser: MediaSession.ControllerInfo,
            parentId: String,
            page: Int,
            pageSize: Int,
            params: LibraryParams?
        ) = Futures.immediateFuture(LibraryResult.ofItemList(ImmutableList.of(), null))

        // onGetItem: default implementation returns RESULT_ERROR_NOT_SUPPORTED — sufficient for now
    }

    override fun onCreate() {
        super.onCreate()

        // Build a DataSource.Factory that reads the access token fresh for each stream request
        val dataSourceFactory = DefaultHttpDataSource.Factory().apply {
            setDefaultRequestProperties(
                mapOf("Authorization" to "Bearer ${tokenStorage.accessToken.orEmpty()}")
            )
            setConnectTimeoutMs(15_000)
            setReadTimeoutMs(15_000)
        }

        player = ExoPlayer.Builder(this)
            .setMediaSourceFactory(
                DefaultMediaSourceFactory(this)
                    .setDataSourceFactory(dataSourceFactory)
            )
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(C.USAGE_MEDIA)
                    .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
                    .build(),
                /* handleAudioFocus= */ true
            )
            .setHandleAudioBecomingNoisy(true) // Pause on headphone unplug
            .build()

        player.addListener(playerListener)

        // PendingIntent so tapping the notification opens MainActivity
        val activityIntent = Intent(this, MainActivity::class.java)
            .apply { flags = Intent.FLAG_ACTIVITY_SINGLE_TOP }
        val pendingIntent = PendingIntent.getActivity(
            this, 0, activityIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        mediaSession = MediaLibrarySession.Builder(this, player, libraryCallback)
            .setSessionActivity(pendingIntent)
            .build()
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaLibrarySession =
        mediaSession

    override fun onTaskRemoved(rootIntent: Intent?) {
        // Stop service when app is swiped away and nothing is playing
        if (!player.playWhenReady || player.mediaItemCount == 0) {
            stopSelf()
        }
    }

    override fun onDestroy() {
        mediaSession.release()
        player.removeListener(playerListener)
        player.release()
        serviceScope.cancel()
        super.onDestroy()
    }
}
