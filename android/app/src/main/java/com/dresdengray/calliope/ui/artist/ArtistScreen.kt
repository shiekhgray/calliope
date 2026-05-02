package com.dresdengray.calliope.ui.artist

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.dresdengray.calliope.playback.PlayerViewModel
import com.dresdengray.calliope.ui.common.AlbumCard
import com.dresdengray.calliope.ui.common.ErrorBox
import com.dresdengray.calliope.ui.common.LoadingBox
import com.dresdengray.calliope.ui.common.TrackRow
import com.dresdengray.calliope.ui.common.UiState
import com.dresdengray.calliope.ui.player.MiniPlayerBar

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ArtistScreen(
    playerViewModel: PlayerViewModel,
    onNavigateBack: () -> Unit,
    onNavigateToAlbum: (Int) -> Unit,
    onOpenNowPlaying: () -> Unit,
    viewModel: ArtistViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()
    val artistName = (state as? UiState.Success)?.data?.artistName ?: ""
    val playerState by playerViewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(artistName) },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        },
        bottomBar = {
            if (playerState.currentTrack != null) {
                MiniPlayerBar(
                    uiState = playerState,
                    onTogglePlayPause = playerViewModel::togglePlayPause,
                    onTap = onOpenNowPlaying,
                    modifier = Modifier.navigationBarsPadding()
                )
            }
        }
    ) { padding ->
        when (val s = state) {
            is UiState.Loading -> LoadingBox()
            is UiState.Error -> ErrorBox(message = s.message, onRetry = viewModel::load)
            is UiState.Success -> ArtistContent(
                data = s.data,
                onNavigateToAlbum = onNavigateToAlbum,
                onPlayTrack = { index ->
                    val tracks = s.data.topTracks
                    // Enrich top tracks with artist info before playing
                    val enriched = tracks.map { t ->
                        if (t.artistId == 0) t.copy(
                            artistId = tracks.firstOrNull { it.artistId != 0 }?.artistId ?: 0,
                            artistName = s.data.artistName
                        ) else t
                    }
                    playerViewModel.playQueue(enriched, index)
                },
                modifier = Modifier.padding(padding)
            )
        }
    }
}

@Composable
private fun ArtistContent(
    data: ArtistUiData,
    onNavigateToAlbum: (Int) -> Unit,
    onPlayTrack: (Int) -> Unit,
    modifier: Modifier = Modifier
) {
    LazyVerticalGrid(
        columns = GridCells.Fixed(2),
        contentPadding = PaddingValues(8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        modifier = modifier.fillMaxSize()
    ) {
        if (data.topTracks.isNotEmpty()) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                SectionHeader("Top Tracks")
            }
            items(
                items = data.topTracks,
                span = { GridItemSpan(maxLineSpan) }
            ) { track ->
                val index = data.topTracks.indexOf(track)
                TrackRow(
                    track = track,
                    onClick = { onPlayTrack(index) }
                )
                HorizontalDivider()
            }
        }

        if (data.albums.isNotEmpty()) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                SectionHeader("Albums")
            }
            items(data.albums) { album ->
                AlbumCard(album = album, onClick = { onNavigateToAlbum(album.id) })
            }
        }
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
