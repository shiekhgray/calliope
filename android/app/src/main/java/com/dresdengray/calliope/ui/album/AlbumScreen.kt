package com.dresdengray.calliope.ui.album

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import coil.compose.AsyncImage
import com.dresdengray.calliope.data.api.model.AlbumDetail
import com.dresdengray.calliope.data.api.model.Track
import com.dresdengray.calliope.playback.PlayerViewModel
import com.dresdengray.calliope.ui.common.AddToPlaylistSheet
import com.dresdengray.calliope.ui.common.ErrorBox
import com.dresdengray.calliope.ui.common.LoadingBox
import com.dresdengray.calliope.ui.common.TrackRow
import com.dresdengray.calliope.ui.common.UiState
import com.dresdengray.calliope.ui.player.MiniPlayerBar
import com.dresdengray.calliope.util.Constants

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AlbumScreen(
    playerViewModel: PlayerViewModel,
    onNavigateBack: () -> Unit,
    onNavigateToArtist: (Int) -> Unit,
    onOpenNowPlaying: () -> Unit,
    viewModel: AlbumViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()
    val playerState by playerViewModel.uiState.collectAsState()
    var addToPlaylistTrack: Track? by remember { mutableStateOf(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { },
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
            is UiState.Success -> AlbumContent(
                album = s.data,
                onNavigateToArtist = onNavigateToArtist,
                onPlayTrack = { index -> playerViewModel.playQueue(s.data.tracks, index) },
                onAddToPlaylist = { track -> addToPlaylistTrack = track },
                modifier = Modifier.padding(padding)
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
private fun AlbumContent(
    album: AlbumDetail,
    onNavigateToArtist: (Int) -> Unit,
    onPlayTrack: (Int) -> Unit,
    onAddToPlaylist: (Track) -> Unit,
    modifier: Modifier = Modifier
) {
    LazyColumn(modifier = modifier.fillMaxSize()) {
        item {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 24.dp, vertical = 16.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                AsyncImage(
                    model = Constants.albumArtUrl(album.id),
                    contentDescription = album.title,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .size(280.dp)
                        .clip(RoundedCornerShape(8.dp))
                )
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    text = album.title,
                    style = MaterialTheme.typography.headlineSmall,
                    textAlign = TextAlign.Center
                )
                TextButton(onClick = { onNavigateToArtist(album.artistId) }) {
                    Text(album.artistName)
                }
                if (album.year != null) {
                    Text(
                        text = album.year.toString(),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            HorizontalDivider()
        }

        itemsIndexed(album.tracks, key = { _, track -> track.id }) { index, track ->
            TrackRow(
                track = track,
                onClick = { onPlayTrack(index) },
                onAddToPlaylist = { onAddToPlaylist(track) }
            )
            HorizontalDivider(modifier = Modifier.padding(start = 56.dp))
        }
    }
}
