package com.dresdengray.calliope.playback

import android.net.Uri
import android.os.Bundle
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import com.dresdengray.calliope.data.api.model.Track
import com.dresdengray.calliope.util.Constants
import java.io.File

// ---------------------------------------------------------------------------
// Playable MediaItem construction (shared by PlayerViewModel + MusicService)
//
// Playable items always use the plain track id as their mediaId so that:
//   - play-count reporting (MusicService.playerListener) can parse it via toIntOrNull()
//   - PlayerViewModel.toTrack() can reconstruct the Track when its local queue is lost
// The Android Auto *browse* tree uses the richer node-ID scheme below; those node
// IDs only live on browsable/playable browse items, never on the actual queue items.
// ---------------------------------------------------------------------------

/** Build a playable queue MediaItem, substituting a downloaded local file when [localFilePath] is set. */
internal fun Track.toMediaItem(localFilePath: String? = null): MediaItem {
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
                .setIsBrowsable(false)
                .setIsPlayable(true)
                .setExtras(extras)
                .build()
        )
        .build()
}

// ---------------------------------------------------------------------------
// Android Auto browse tree — node-ID scheme + parsing
// ---------------------------------------------------------------------------

object BrowseTree {
    const val ROOT = "root"
    const val ARTISTS = "artists"
    const val PLAYLISTS = "playlists"
    const val RECENTLY_PLAYED = "recently-played"

    fun artist(id: Int) = "artist/$id"
    fun topTracks(artistId: Int) = "artist/$artistId/top-tracks"
    fun album(id: Int) = "album/$id"
    fun playlist(id: Int) = "playlist/$id"

    fun trackInAlbum(trackId: Int, albumId: Int) = "track/$trackId/album/$albumId"
    fun trackInTopTracks(trackId: Int, artistId: Int) = "track/$trackId/artist/$artistId"
    fun trackInPlaylist(trackId: Int, playlistId: Int) = "track/$trackId/playlist/$playlistId"
    fun trackInRecent(trackId: Int) = "track/$trackId/recent"

    /** A parsed track node: which track was tapped and which queue context surrounds it. */
    sealed interface TrackContext {
        val trackId: Int
        data class Album(override val trackId: Int, val albumId: Int) : TrackContext
        data class TopTracks(override val trackId: Int, val artistId: Int) : TrackContext
        data class Playlist(override val trackId: Int, val playlistId: Int) : TrackContext
        data class Recent(override val trackId: Int) : TrackContext
    }

    /** Parse a `track/...` node ID into its context, or null if [nodeId] is not a track node. */
    fun parseTrack(nodeId: String): TrackContext? {
        val parts = nodeId.split("/")
        if (parts.getOrNull(0) != "track") return null
        val trackId = parts.getOrNull(1)?.toIntOrNull() ?: return null
        return when (parts.getOrNull(2)) {
            "album" -> parts.getOrNull(3)?.toIntOrNull()?.let { TrackContext.Album(trackId, it) }
            "artist" -> parts.getOrNull(3)?.toIntOrNull()?.let { TrackContext.TopTracks(trackId, it) }
            "playlist" -> parts.getOrNull(3)?.toIntOrNull()?.let { TrackContext.Playlist(trackId, it) }
            "recent" -> TrackContext.Recent(trackId)
            else -> null
        }
    }
}

/** Build a browsable folder item (no URI, isBrowsable = true). */
internal fun browseFolder(
    id: String,
    title: String,
    subtitle: String? = null,
    artworkUri: Uri? = null,
    mediaType: Int = MediaMetadata.MEDIA_TYPE_FOLDER_MIXED,
): MediaItem = MediaItem.Builder()
    .setMediaId(id)
    .setMediaMetadata(
        MediaMetadata.Builder()
            .setTitle(title)
            .setSubtitle(subtitle)
            .setArtworkUri(artworkUri)
            .setIsBrowsable(true)
            .setIsPlayable(false)
            .setMediaType(mediaType)
            .build()
    )
    .build()

/**
 * Build a playable *browse* item for the Auto tree: carries the [nodeId] (so the queue
 * context can be recovered when tapped) and display metadata, but no URI. The real,
 * URI-backed queue item is produced later by [toMediaItem] during resolution.
 */
internal fun Track.toBrowsableItem(nodeId: String): MediaItem = MediaItem.Builder()
    .setMediaId(nodeId)
    .setMediaMetadata(
        MediaMetadata.Builder()
            .setTitle(title)
            .setArtist(artistName)
            .setAlbumTitle(albumTitle)
            .setArtworkUri(Uri.parse(Constants.albumArtUrl(albumId)))
            .setIsBrowsable(false)
            .setIsPlayable(true)
            .setMediaType(MediaMetadata.MEDIA_TYPE_MUSIC)
            .build()
    )
    .build()
