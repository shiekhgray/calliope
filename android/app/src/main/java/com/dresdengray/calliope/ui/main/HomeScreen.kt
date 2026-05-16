package com.dresdengray.calliope.ui.main

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Radio
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.dresdengray.calliope.data.api.model.Track
import com.dresdengray.calliope.playback.PlayerUiState
import com.dresdengray.calliope.playback.PlayerViewModel
import com.dresdengray.calliope.ui.common.TrackRow
import com.dresdengray.calliope.ui.common.formatDuration
import com.dresdengray.calliope.ui.library.LibraryContent
import com.dresdengray.calliope.ui.settings.SettingsSheet
import com.dresdengray.calliope.util.Constants

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    playerViewModel: PlayerViewModel,
    onNavigateToArtist: (Int) -> Unit,
    onLogout: () -> Unit
) {
    val uiState by playerViewModel.uiState.collectAsState()
    val similarTracks by playerViewModel.similarTracks.collectAsState()
    val radioMode by playerViewModel.radioMode.collectAsState()
    var showSettings by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(if (uiState.currentTrack == null) "Library" else "Now Playing") },
                actions = {
                    IconButton(onClick = { showSettings = true }) {
                        Icon(Icons.Filled.Settings, contentDescription = "Settings")
                    }
                }
            )
        }
    ) { padding ->
        if (uiState.currentTrack == null) {
            // State A: no track — show library artist list
            LibraryContent(
                onNavigateToArtist = onNavigateToArtist,
                contentPadding = padding
            )
        } else {
            // State B: track playing — show full now-playing content
            HomeNowPlayingContent(
                uiState = uiState,
                similarTracks = similarTracks,
                radioMode = radioMode,
                contentPadding = padding,
                onTogglePlayPause = playerViewModel::togglePlayPause,
                onSkipPrev = playerViewModel::skipToPrev,
                onSkipNext = playerViewModel::skipToNext,
                onStop = playerViewModel::stopPlayback,
                onSeek = playerViewModel::seekTo,
                onToggleRadioMode = playerViewModel::toggleRadioMode,
                onPlaySimilarTrack = { track -> playerViewModel.playQueue(listOf(track)) }
            )
        }
    }

    if (showSettings) {
        SettingsSheet(
            onDismiss = { showSettings = false },
            onLogout = onLogout
        )
    }
}

@Composable
fun HomeNowPlayingContent(
    uiState: PlayerUiState,
    similarTracks: List<Track>,
    radioMode: Boolean,
    contentPadding: PaddingValues,
    onTogglePlayPause: () -> Unit,
    onSkipPrev: () -> Unit,
    onSkipNext: () -> Unit,
    onStop: () -> Unit,
    onSeek: (Long) -> Unit,
    onToggleRadioMode: () -> Unit,
    onPlaySimilarTrack: (Track) -> Unit
) {
    val track = uiState.currentTrack ?: return

    var isScrubbing by remember { mutableStateOf(false) }
    var scrubPosition by remember { mutableFloatStateOf(0f) }

    val sliderValue = if (isScrubbing) scrubPosition else {
        if (uiState.durationMs > 0) uiState.positionMs.toFloat() / uiState.durationMs.toFloat()
        else 0f
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(contentPadding),
        contentPadding = PaddingValues(bottom = 24.dp)
    ) {
        item {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Spacer(Modifier.height(16.dp))

                // Album art
                AsyncImage(
                    model = Constants.albumArtUrl(track.albumId),
                    contentDescription = track.title,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .size(300.dp)
                        .clip(RoundedCornerShape(12.dp))
                )

                Spacer(Modifier.height(32.dp))

                // Track info
                Text(
                    text = track.title,
                    style = MaterialTheme.typography.titleLarge,
                    textAlign = TextAlign.Center,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text = track.artistName,
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                if (track.albumTitle.isNotBlank()) {
                    Text(
                        text = track.albumTitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }

                Spacer(Modifier.height(24.dp))

                // Scrubber
                Slider(
                    value = sliderValue.coerceIn(0f, 1f),
                    onValueChange = { v ->
                        isScrubbing = true
                        scrubPosition = v
                    },
                    onValueChangeFinished = {
                        onSeek((scrubPosition * uiState.durationMs).toLong())
                        isScrubbing = false
                    },
                    modifier = Modifier.fillMaxWidth()
                )

                // Time labels
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    val displayPosition = if (isScrubbing) {
                        (scrubPosition * uiState.durationMs).toLong()
                    } else uiState.positionMs
                    Text(
                        text = formatDuration(displayPosition),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = formatDuration(uiState.durationMs),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                Spacer(Modifier.height(16.dp))

                // Transport controls: Prev | Play/Pause | Stop | Next
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    IconButton(onClick = onSkipPrev, modifier = Modifier.size(56.dp)) {
                        Icon(
                            imageVector = Icons.Filled.SkipPrevious,
                            contentDescription = "Previous",
                            modifier = Modifier.size(40.dp)
                        )
                    }
                    IconButton(
                        onClick = onTogglePlayPause,
                        modifier = Modifier.size(72.dp)
                    ) {
                        Icon(
                            imageVector = if (uiState.isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                            contentDescription = if (uiState.isPlaying) "Pause" else "Play",
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(56.dp)
                        )
                    }
                    IconButton(onClick = onStop, modifier = Modifier.size(56.dp)) {
                        Icon(
                            imageVector = Icons.Filled.Stop,
                            contentDescription = "Stop",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(40.dp)
                        )
                    }
                    IconButton(onClick = onSkipNext, modifier = Modifier.size(56.dp)) {
                        Icon(
                            imageVector = Icons.Filled.SkipNext,
                            contentDescription = "Next",
                            modifier = Modifier.size(40.dp)
                        )
                    }
                }

                Spacer(Modifier.height(16.dp))

                // Radio mode toggle
                FilterChip(
                    selected = radioMode,
                    onClick = onToggleRadioMode,
                    label = { Text("Radio") },
                    leadingIcon = {
                        Icon(
                            Icons.Filled.Radio,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                )

                Spacer(Modifier.height(24.dp))
            }
        }

        // Up Next queue section
        val upNextTracks = if (uiState.currentIndex >= 0 && uiState.currentIndex + 1 < uiState.queueTracks.size) {
            uiState.queueTracks.drop(uiState.currentIndex + 1)
        } else emptyList()

        if (upNextTracks.isNotEmpty()) {
            item {
                HorizontalDivider(modifier = Modifier.padding(horizontal = 16.dp))
                Text(
                    text = "Up Next",
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)
                )
            }
            items(upNextTracks) { queued ->
                TrackRow(
                    track = queued,
                    onClick = {}
                )
            }
        }

        // Previously Played queue section
        val previousTracks = if (uiState.currentIndex > 0) {
            uiState.queueTracks.take(uiState.currentIndex)
        } else emptyList()

        if (previousTracks.isNotEmpty()) {
            item {
                HorizontalDivider(modifier = Modifier.padding(horizontal = 16.dp))
                Text(
                    text = "Previously Played",
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)
                )
            }
            items(previousTracks) { prev ->
                TrackRow(
                    track = prev,
                    onClick = {}
                )
            }
        }

        if (similarTracks.isNotEmpty()) {
            item {
                HorizontalDivider(modifier = Modifier.padding(horizontal = 16.dp))
                Text(
                    text = "Similar Tracks",
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)
                )
            }

            items(similarTracks) { similar ->
                TrackRow(
                    track = similar,
                    onClick = { onPlaySimilarTrack(similar) }
                )
            }
        }
    }
}
