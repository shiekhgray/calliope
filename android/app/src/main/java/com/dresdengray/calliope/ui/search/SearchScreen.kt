package com.dresdengray.calliope.ui.search

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.SuggestionChipDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.dresdengray.calliope.data.api.model.Album
import com.dresdengray.calliope.data.api.model.Artist
import com.dresdengray.calliope.data.api.model.SearchHistoryEntry
import com.dresdengray.calliope.data.api.model.SearchResults
import com.dresdengray.calliope.data.api.model.Track
import com.dresdengray.calliope.playback.PlayerViewModel
import com.dresdengray.calliope.ui.common.AddToPlaylistSheet
import com.dresdengray.calliope.ui.common.AlbumCard
import com.dresdengray.calliope.ui.common.ErrorBox
import com.dresdengray.calliope.ui.common.LoadingBox
import com.dresdengray.calliope.ui.common.TrackRow
import com.dresdengray.calliope.ui.common.UiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SearchScreen(
    playerViewModel: PlayerViewModel,
    onNavigateToArtist: (Int) -> Unit,
    onNavigateToAlbum: (Int) -> Unit,
    viewModel: SearchViewModel = hiltViewModel()
) {
    val query by viewModel.query.collectAsState()
    val results by viewModel.results.collectAsState()
    val history by viewModel.history.collectAsState()
    var addToPlaylistTrack: Track? by remember { mutableStateOf(null) }

    Column(modifier = Modifier.fillMaxSize()) {
        OutlinedTextField(
            value = query,
            onValueChange = viewModel::setQuery,
            placeholder = { Text("Artists, albums, tracks…") },
            leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
            trailingIcon = {
                if (query.isNotEmpty()) {
                    IconButton(onClick = { viewModel.setQuery("") }) {
                        Icon(Icons.Filled.Clear, contentDescription = "Clear")
                    }
                }
            },
            singleLine = true,
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp)
        )

        when (val r = results) {
            null -> {
                // No active query — show recent searches if any
                if (history.isNotEmpty()) {
                    RecentSearches(
                        history = history,
                        onArtistClick = { id ->
                            viewModel.recordHistory("artist", id)
                            onNavigateToArtist(id)
                        },
                        onAlbumClick = { id ->
                            viewModel.recordHistory("album", id)
                            onNavigateToAlbum(id)
                        },
                        onTrackClick = { entry ->
                            viewModel.recordHistory("track", entry.entityId)
                            playerViewModel.playQueue(listOf(entry.toTrack()))
                        }
                    )
                }
            }
            is UiState.Loading -> LoadingBox()
            is UiState.Error -> ErrorBox(message = r.message, onRetry = viewModel::retry)
            is UiState.Success -> ResultsList(
                results = r.data,
                query = query,
                onArtistClick = { artist ->
                    viewModel.recordHistory("artist", artist.id)
                    onNavigateToArtist(artist.id)
                },
                onAlbumClick = { album ->
                    viewModel.recordHistory("album", album.id)
                    onNavigateToAlbum(album.id)
                },
                onTrackClick = { track ->
                    viewModel.recordHistory("track", track.id)
                    playerViewModel.playQueue(listOf(track))
                },
                onAddToPlaylist = { track -> addToPlaylistTrack = track }
            )
        }
    }

    addToPlaylistTrack?.let { track ->
        AddToPlaylistSheet(
            track = track,
            onDismiss = { addToPlaylistTrack = null }
        )
    }
}

@Composable
private fun RecentSearches(
    history: List<SearchHistoryEntry>,
    onArtistClick: (Int) -> Unit,
    onAlbumClick: (Int) -> Unit,
    onTrackClick: (SearchHistoryEntry) -> Unit
) {
    Column(modifier = Modifier.padding(horizontal = 16.dp)) {
        Text(
            text = "Recent",
            style = MaterialTheme.typography.titleSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(vertical = 8.dp)
        )
        // Simple wrap-flow using FlowRow would be nicer, but Material3 FlowRow requires
        // ExperimentalLayoutApi and we can keep it simple with a vertically-stacked
        // chip column. If wrapping is desired later, swap to FlowRow.
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            history.forEach { entry ->
                val label = when (entry.entityType) {
                    "artist" -> entry.name
                    "album" -> "${entry.artistName ?: "?"} — ${entry.name}"
                    "track" -> "${entry.artistName ?: "?"} — ${entry.name}"
                    else -> entry.name
                }
                SuggestionChip(
                    onClick = {
                        when (entry.entityType) {
                            "artist" -> onArtistClick(entry.entityId)
                            "album" -> onAlbumClick(entry.entityId)
                            "track" -> onTrackClick(entry)
                        }
                    },
                    label = {
                        Text(
                            text = label,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    },
                    colors = SuggestionChipDefaults.suggestionChipColors()
                )
            }
        }
    }
}

@Composable
private fun ResultsList(
    results: SearchResults,
    query: String,
    onArtistClick: (Artist) -> Unit,
    onAlbumClick: (Album) -> Unit,
    onTrackClick: (Track) -> Unit,
    onAddToPlaylist: (Track) -> Unit
) {
    val empty = results.artists.isEmpty() && results.albums.isEmpty() && results.tracks.isEmpty()
    if (empty) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp),
            verticalArrangement = Arrangement.Top,
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = "No results for \"$query\"",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        return
    }

    LazyVerticalGrid(
        columns = GridCells.Fixed(2),
        contentPadding = PaddingValues(8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        modifier = Modifier.fillMaxSize()
    ) {
        if (results.artists.isNotEmpty()) {
            item(span = { GridItemSpan(maxLineSpan) }) { SectionHeader("Artists") }
            items(
                items = results.artists,
                span = { GridItemSpan(maxLineSpan) },
                key = { "artist-${it.id}" }
            ) { artist ->
                ArtistResultRow(artist = artist, onClick = { onArtistClick(artist) })
                HorizontalDivider()
            }
        }

        if (results.albums.isNotEmpty()) {
            item(span = { GridItemSpan(maxLineSpan) }) { SectionHeader("Albums") }
            items(items = results.albums, key = { "album-${it.id}" }) { album ->
                Column {
                    AlbumCard(album = album, onClick = { onAlbumClick(album) })
                    Text(
                        text = album.artistName,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.padding(start = 8.dp, top = 2.dp, end = 8.dp)
                    )
                }
            }
        }

        if (results.tracks.isNotEmpty()) {
            item(span = { GridItemSpan(maxLineSpan) }) { SectionHeader("Tracks") }
            items(
                items = results.tracks,
                span = { GridItemSpan(maxLineSpan) },
                key = { "track-${it.id}" }
            ) { track ->
                TrackRow(
                    track = track,
                    onClick = { onTrackClick(track) },
                    onAddToPlaylist = { onAddToPlaylist(track) }
                )
                HorizontalDivider()
            }
        }
    }
}

@Composable
private fun ArtistResultRow(artist: Artist, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = artist.name,
            style = MaterialTheme.typography.bodyLarge,
            modifier = Modifier.fillMaxWidth()
        )
    }
}

@Composable
private fun SectionHeader(title: String) {
    Text(
        text = title,
        style = MaterialTheme.typography.titleMedium,
        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
    )
}

/**
 * History entries for tracks carry enough info to play the track without
 * a full Track payload. ArtistId is missing from the API response, so the
 * mini-player's "artist" link won't be clickable for history-tapped tracks
 * until the user navigates to the artist via another path. This matches
 * the web behavior.
 */
private fun SearchHistoryEntry.toTrack(): Track = Track(
    id = entityId,
    title = name,
    trackNumber = null,
    durationMs = null,
    bitrateKbps = null,
    format = null,
    playCount = 0,
    albumId = albumId ?: 0,
    albumTitle = albumTitle ?: "",
    artistId = artistId ?: 0,
    artistName = artistName ?: ""
)
