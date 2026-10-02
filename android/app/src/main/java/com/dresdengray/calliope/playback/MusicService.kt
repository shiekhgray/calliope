package com.dresdengray.calliope.playback

import android.app.PendingIntent
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.okhttp.OkHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.session.CommandButton
import androidx.media3.session.LibraryResult
import androidx.media3.session.MediaLibraryService
import androidx.media3.session.MediaSession
import androidx.media3.session.SessionCommand
import androidx.media3.session.SessionResult
import com.dresdengray.calliope.MainActivity
import com.dresdengray.calliope.R
import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.api.model.Track
import com.dresdengray.calliope.util.Constants
import com.google.common.collect.ImmutableList
import com.google.common.util.concurrent.Futures
import com.google.common.util.concurrent.ListenableFuture
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.guava.future
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import javax.inject.Inject

@AndroidEntryPoint
class MusicService : MediaLibraryService() {

    @Inject lateinit var okHttpClient: OkHttpClient
    @Inject lateinit var api: CalliopeApi
    @Inject lateinit var radioExtender: RadioQueueExtender

    private lateinit var player: ExoPlayer
    private lateinit var mediaSession: MediaLibrarySession

    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    // Play count tracking: report only on natural track completion
    private var currentTrackId: Int? = null
    private val reportedThisSession = mutableSetOf<Int>()

    // Radio mode (Android Auto). On by default; only auto-extends queues that were
    // started from the Auto browse tree (not the phone UI, which manages its own radio).
    @Volatile private var radioModeEnabled = true
    @Volatile private var autoInitiatedPlayback = false
    // Tracks seen this radio session — seeded with the manual queue, grows as radio appends.
    private val radioPlayedIds = mutableSetOf<Int>()

    companion object {
        private const val CMD_TOGGLE_RADIO = "com.dresdengray.calliope.TOGGLE_RADIO"
    }

    private val playerListener = object : Player.Listener {
        override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
            if (reason == Player.MEDIA_ITEM_TRANSITION_REASON_AUTO) {
                // Previous track finished naturally — report it
                currentTrackId?.let { reportPlayCount(it) }
            }
            currentTrackId = mediaItem?.mediaId?.toIntOrNull()
            if (radioModeEnabled && autoInitiatedPlayback) {
                currentTrackId?.let { maybeExtendRadio(it) }
            }
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

    /** When radio mode is on and the queue is nearly empty, append similar tracks. Call on main thread. */
    private fun maybeExtendRadio(seedTrackId: Int) {
        val remaining = player.mediaItemCount - player.currentMediaItemIndex - 1
        if (remaining > 1) return
        serviceScope.launch {
            val toAppend = radioExtender.nextTracks(seedTrackId, radioPlayedIds.toSet(), max = 5)
            if (toAppend.isEmpty()) return@launch
            val items = toAppend.map { radioExtender.toMediaItem(it) }
            radioPlayedIds.addAll(toAppend.map { it.id })
            withContext(Dispatchers.Main) { items.forEach { player.addMediaItem(it) } }
        }
    }

    // Android Auto browse root item
    private val rootItem = MediaItem.Builder()
        .setMediaId(BrowseTree.ROOT)
        .setMediaMetadata(
            MediaMetadata.Builder()
                .setIsBrowsable(true)
                .setIsPlayable(false)
                .setMediaType(MediaMetadata.MEDIA_TYPE_FOLDER_MIXED)
                .setTitle("Calliope")
                .build()
        )
        .build()

    // ---------------------------------------------------------------------
    // Browse tree
    // ---------------------------------------------------------------------

    private suspend fun childrenOf(parentId: String): List<MediaItem> = when {
        parentId == BrowseTree.ROOT -> listOf(
            browseFolder(BrowseTree.ARTISTS, "Artists", mediaType = MediaMetadata.MEDIA_TYPE_FOLDER_ARTISTS),
            browseFolder(BrowseTree.PLAYLISTS, "Playlists", mediaType = MediaMetadata.MEDIA_TYPE_FOLDER_PLAYLISTS),
            browseFolder(BrowseTree.RECENTLY_PLAYED, "Recently Played"),
        )

        parentId == BrowseTree.ARTISTS ->
            api.getArtists().map {
                browseFolder(BrowseTree.artist(it.id), it.name, mediaType = MediaMetadata.MEDIA_TYPE_ARTIST)
            }

        parentId == BrowseTree.PLAYLISTS ->
            api.getPlaylists().map {
                browseFolder(BrowseTree.playlist(it.id), it.title, mediaType = MediaMetadata.MEDIA_TYPE_PLAYLIST)
            }

        parentId == BrowseTree.RECENTLY_PLAYED ->
            api.getTopTracks(limit = 50).map { it.toBrowsableItem(BrowseTree.trackInRecent(it.id)) }

        parentId.startsWith("artist/") && parentId.endsWith("/top-tracks") -> {
            val artistId = parentId.removePrefix("artist/").removeSuffix("/top-tracks").toIntOrNull()
            if (artistId == null) emptyList()
            else api.getArtistTopTracks(artistId).map {
                it.toBrowsableItem(BrowseTree.trackInTopTracks(it.id, artistId))
            }
        }

        parentId.startsWith("artist/") -> {
            val artistId = parentId.removePrefix("artist/").toIntOrNull()
            if (artistId == null) emptyList()
            else buildList {
                add(browseFolder(BrowseTree.topTracks(artistId), "▶ Top Tracks"))
                addAll(api.getArtistAlbums(artistId).map { album ->
                    browseFolder(
                        BrowseTree.album(album.id),
                        album.title,
                        subtitle = album.year?.toString(),
                        artworkUri = Uri.parse(Constants.albumArtUrl(album.id)),
                        mediaType = MediaMetadata.MEDIA_TYPE_ALBUM,
                    )
                })
            }
        }

        parentId.startsWith("album/") -> {
            val albumId = parentId.removePrefix("album/").toIntOrNull()
            if (albumId == null) emptyList()
            else albumTracks(albumId).map { it.toBrowsableItem(BrowseTree.trackInAlbum(it.id, albumId)) }
        }

        parentId.startsWith("playlist/") -> {
            val playlistId = parentId.removePrefix("playlist/").toIntOrNull()
            if (playlistId == null) emptyList()
            else api.getPlaylist(playlistId).entries.map {
                it.track.toBrowsableItem(BrowseTree.trackInPlaylist(it.track.id, playlistId))
            }
        }

        else -> emptyList()
    }

    /** Album-detail tracks omit album/artist fields — enrich them from the album context. */
    private suspend fun albumTracks(albumId: Int): List<Track> {
        val album = api.getAlbum(albumId)
        return album.tracks.map {
            it.copy(
                albumId = album.id,
                albumTitle = album.title,
                artistId = album.artistId,
                artistName = album.artistName,
            )
        }
    }

    /** Resolve a single browse node (folder or track) to a MediaItem for onGetItem. */
    private suspend fun resolveBrowseItem(mediaId: String): MediaItem? {
        BrowseTree.parseTrack(mediaId)?.let { ctx ->
            val (tracks, idx) = buildQueueForContext(ctx) ?: return null
            return tracks.getOrNull(idx)?.toBrowsableItem(mediaId)
        }
        return when {
            mediaId == BrowseTree.ROOT -> rootItem
            mediaId == BrowseTree.ARTISTS -> browseFolder(BrowseTree.ARTISTS, "Artists")
            mediaId == BrowseTree.PLAYLISTS -> browseFolder(BrowseTree.PLAYLISTS, "Playlists")
            mediaId == BrowseTree.RECENTLY_PLAYED -> browseFolder(BrowseTree.RECENTLY_PLAYED, "Recently Played")
            mediaId.startsWith("artist/") && mediaId.endsWith("/top-tracks") ->
                browseFolder(mediaId, "▶ Top Tracks")
            mediaId.startsWith("artist/") -> {
                val id = mediaId.removePrefix("artist/").toIntOrNull() ?: return null
                val name = api.getArtists().firstOrNull { it.id == id }?.name ?: "Artist"
                browseFolder(mediaId, name, mediaType = MediaMetadata.MEDIA_TYPE_ARTIST)
            }
            mediaId.startsWith("album/") -> {
                val id = mediaId.removePrefix("album/").toIntOrNull() ?: return null
                val album = api.getAlbum(id)
                browseFolder(
                    mediaId, album.title,
                    subtitle = album.year?.toString(),
                    artworkUri = Uri.parse(Constants.albumArtUrl(id)),
                    mediaType = MediaMetadata.MEDIA_TYPE_ALBUM,
                )
            }
            mediaId.startsWith("playlist/") -> {
                val id = mediaId.removePrefix("playlist/").toIntOrNull() ?: return null
                browseFolder(mediaId, api.getPlaylist(id).title, mediaType = MediaMetadata.MEDIA_TYPE_PLAYLIST)
            }
            else -> null
        }
    }

    // ---------------------------------------------------------------------
    // Queue building (resolution of a tapped browse node into a playable queue)
    // ---------------------------------------------------------------------

    /** Resolve a track node into (full context queue, index of the tapped track). */
    private suspend fun buildQueueForContext(ctx: BrowseTree.TrackContext): Pair<List<Track>, Int>? {
        val tracks: List<Track> = runCatching {
            when (ctx) {
                is BrowseTree.TrackContext.Album -> albumTracks(ctx.albumId)
                is BrowseTree.TrackContext.TopTracks -> api.getArtistTopTracks(ctx.artistId)
                is BrowseTree.TrackContext.Playlist -> api.getPlaylist(ctx.playlistId).entries.map { it.track }
                is BrowseTree.TrackContext.Recent -> api.getTopTracks(limit = 50)
            }
        }.getOrDefault(emptyList())
        if (tracks.isEmpty()) return null
        val idx = tracks.indexOfFirst { it.id == ctx.trackId }.coerceAtLeast(0)
        return tracks to idx
    }

    /** Resolve a single mediaId-only browse item into a playable, URI-backed queue item. */
    private suspend fun resolvePlayable(mediaId: String): MediaItem? {
        val ctx = BrowseTree.parseTrack(mediaId) ?: return null
        val (tracks, idx) = buildQueueForContext(ctx) ?: return null
        return tracks.getOrNull(idx)?.let { radioExtender.toMediaItem(it) }
    }

    // ---------------------------------------------------------------------
    // Custom action: radio toggle
    // ---------------------------------------------------------------------

    private fun buildCustomLayout(): List<CommandButton> {
        val on = radioModeEnabled
        return listOf(
            CommandButton.Builder()
                .setSessionCommand(SessionCommand(CMD_TOGGLE_RADIO, Bundle.EMPTY))
                .setDisplayName(if (on) "Radio: On" else "Radio: Off")
                .setIconResId(if (on) R.drawable.ic_radio_on else R.drawable.ic_radio_off)
                .build()
        )
    }

    private val libraryCallback = object : MediaLibrarySession.Callback {

        override fun onConnect(
            session: MediaSession,
            controller: MediaSession.ControllerInfo
        ): MediaSession.ConnectionResult {
            val base = super.onConnect(session, controller)
            val sessionCommands = base.availableSessionCommands.buildUpon()
                .add(SessionCommand(CMD_TOGGLE_RADIO, Bundle.EMPTY))
                .build()
            return MediaSession.ConnectionResult.accept(sessionCommands, base.availablePlayerCommands)
        }

        override fun onCustomCommand(
            session: MediaSession,
            controller: MediaSession.ControllerInfo,
            customCommand: SessionCommand,
            args: Bundle
        ): ListenableFuture<SessionResult> {
            if (customCommand.customAction == CMD_TOGGLE_RADIO) {
                radioModeEnabled = !radioModeEnabled
                mediaSession.setCustomLayout(buildCustomLayout())
                if (radioModeEnabled && autoInitiatedPlayback) {
                    currentTrackId?.let { maybeExtendRadio(it) }
                }
                return Futures.immediateFuture(SessionResult(SessionResult.RESULT_SUCCESS))
            }
            return Futures.immediateFuture(SessionResult(SessionResult.RESULT_ERROR_NOT_SUPPORTED))
        }

        override fun onGetLibraryRoot(
            session: MediaLibrarySession,
            browser: MediaSession.ControllerInfo,
            params: LibraryParams?
        ) = Futures.immediateFuture(LibraryResult.ofItem(rootItem, params))

        override fun onGetChildren(
            session: MediaLibrarySession,
            browser: MediaSession.ControllerInfo,
            parentId: String,
            page: Int,
            pageSize: Int,
            params: LibraryParams?
        ): ListenableFuture<LibraryResult<ImmutableList<MediaItem>>> = serviceScope.future {
            val children = runCatching { childrenOf(parentId) }.getOrDefault(emptyList())
            LibraryResult.ofItemList(ImmutableList.copyOf(children), params)
        }

        override fun onGetItem(
            session: MediaLibrarySession,
            browser: MediaSession.ControllerInfo,
            mediaId: String
        ): ListenableFuture<LibraryResult<MediaItem>> = serviceScope.future {
            val item = runCatching { resolveBrowseItem(mediaId) }.getOrNull()
            if (item != null) LibraryResult.ofItem(item, null)
            else LibraryResult.ofError(LibraryResult.RESULT_ERROR_BAD_VALUE)
        }

        override fun onSetMediaItems(
            mediaSession: MediaSession,
            controller: MediaSession.ControllerInfo,
            mediaItems: MutableList<MediaItem>,
            startIndex: Int,
            startPositionMs: Long
        ): ListenableFuture<MediaSession.MediaItemsWithStartPosition> = serviceScope.future {
            // Our own phone UI supplies fully-formed, URI-backed items — play as-is and
            // leave radio extension to PlayerViewModel.
            if (controller.packageName == packageName) {
                autoInitiatedPlayback = false
                return@future MediaSession.MediaItemsWithStartPosition(mediaItems, startIndex, startPositionMs)
            }
            // External controller (Android Auto): expand the tapped node into its full queue.
            val tappedId = mediaItems.getOrNull(startIndex)?.mediaId
                ?: mediaItems.firstOrNull()?.mediaId
            val expanded = tappedId?.let { id ->
                BrowseTree.parseTrack(id)?.let { buildQueueForContext(it) }
            }
            if (expanded == null) {
                autoInitiatedPlayback = false
                return@future MediaSession.MediaItemsWithStartPosition(mediaItems, startIndex, startPositionMs)
            }
            val (tracks, idx) = expanded
            val items = tracks.map { radioExtender.toMediaItem(it) }
            autoInitiatedPlayback = true
            radioPlayedIds.clear()
            radioPlayedIds.addAll(tracks.map { it.id })
            MediaSession.MediaItemsWithStartPosition(items, idx, 0L)
        }

        override fun onAddMediaItems(
            mediaSession: MediaSession,
            controller: MediaSession.ControllerInfo,
            mediaItems: MutableList<MediaItem>
        ): ListenableFuture<MutableList<MediaItem>> = serviceScope.future {
            if (controller.packageName == packageName) return@future mediaItems
            mediaItems.map { item ->
                if (item.localConfiguration != null) item
                else resolvePlayable(item.mediaId) ?: item
            }.toMutableList()
        }
    }

    override fun onCreate() {
        super.onCreate()

        // Stream through the app's authenticated OkHttpClient so every request picks up the
        // current access token (AuthInterceptor) and gets a refresh-and-retry on 401
        // (TokenAuthenticator). The previous DefaultHttpDataSource baked one token into an
        // immutable header map here in onCreate(), which went stale after 15 minutes and had no
        // way to recover. Timeouts come from the client (15s connect / 30s read).
        // DefaultDataSource wraps the HTTP factory so file:// URIs (downloaded tracks) also work.
        val httpDataSourceFactory = OkHttpDataSource.Factory(okHttpClient)
        val dataSourceFactory = DefaultDataSource.Factory(this, httpDataSourceFactory)

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

        // Surface the radio toggle on the Auto Now Playing card.
        mediaSession.setCustomLayout(buildCustomLayout())
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
