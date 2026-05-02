package com.dresdengray.calliope.ui.playlist

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.AlertDialog
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.dresdengray.calliope.data.api.model.PlaylistEntry
import com.dresdengray.calliope.data.api.model.Track
import com.dresdengray.calliope.playback.PlayerViewModel
import com.dresdengray.calliope.ui.common.AddToPlaylistSheet
import com.dresdengray.calliope.ui.common.ErrorBox
import com.dresdengray.calliope.ui.common.LoadingBox
import com.dresdengray.calliope.ui.common.TrackRow
import com.dresdengray.calliope.ui.common.UiState
import com.dresdengray.calliope.ui.player.MiniPlayerBar

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PlaylistDetailScreen(
    playerViewModel: PlayerViewModel,
    onNavigateBack: () -> Unit,
    viewModel: PlaylistDetailViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()
    val playerState by playerViewModel.uiState.collectAsState()
    var editMode by remember { mutableStateOf(false) }
    var showDeleteConfirm by remember { mutableStateOf(false) }
    var addToPlaylistTrack: Track? by remember { mutableStateOf(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = (state as? UiState.Success)?.data?.title ?: "Playlist",
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { editMode = !editMode }) {
                        Icon(
                            imageVector = if (editMode) Icons.Filled.Check else Icons.Filled.Edit,
                            contentDescription = if (editMode) "Done editing" else "Edit order"
                        )
                    }
                    IconButton(onClick = { showDeleteConfirm = true }) {
                        Icon(Icons.Filled.Delete, contentDescription = "Delete playlist")
                    }
                }
            )
        },
        bottomBar = {
            if (playerState.currentTrack != null) {
                MiniPlayerBar(
                    uiState = playerState,
                    onTogglePlayPause = playerViewModel::togglePlayPause,
                    onTap = { /* no nav to now-playing from here; user can tap mini-bar on main screen */ },
                    modifier = Modifier.navigationBarsPadding()
                )
            }
        }
    ) { padding ->
        when (val s = state) {
            is UiState.Loading -> LoadingBox()
            is UiState.Error -> ErrorBox(message = s.message, onRetry = viewModel::load)
            is UiState.Success -> {
                val entries = s.data.entries.sortedBy { it.position }
                val tracks = entries.map { it.track }

                if (entries.isEmpty()) {
                    Box(
                        modifier = Modifier
                            .padding(padding)
                            .fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "No tracks yet. Add some from any album or search result.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(32.dp)
                        )
                    }
                } else {
                    LazyColumn(modifier = Modifier.padding(padding).fillMaxSize()) {
                        itemsIndexed(entries, key = { _, e -> e.id }) { idx, entry ->
                            if (editMode) {
                                EditableTrackRow(
                                    entry = entry,
                                    isFirst = idx == 0,
                                    isLast = idx == entries.lastIndex,
                                    onMoveUp = { viewModel.moveTrackUp(entry.track.id) },
                                    onMoveDown = { viewModel.moveTrackDown(entry.track.id) },
                                    onRemove = { viewModel.removeTrack(entry.track.id) }
                                )
                            } else {
                                TrackRow(
                                    track = entry.track,
                                    onClick = { playerViewModel.playQueue(tracks, idx) },
                                    onAddToPlaylist = { addToPlaylistTrack = entry.track }
                                )
                            }
                            HorizontalDivider(modifier = Modifier.padding(start = if (editMode) 0.dp else 56.dp))
                        }
                    }
                }
            }
        }
    }

    addToPlaylistTrack?.let { track ->
        AddToPlaylistSheet(
            track = track,
            onDismiss = { addToPlaylistTrack = null }
        )
    }

    if (showDeleteConfirm) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirm = false },
            title = { Text("Delete playlist?") },
            text = { Text("This cannot be undone.") },
            confirmButton = {
                TextButton(onClick = {
                    showDeleteConfirm = false
                    viewModel.deletePlaylist(onDeleted = onNavigateBack)
                }) {
                    Text("Delete", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteConfirm = false }) { Text("Cancel") }
            }
        )
    }
}

@Composable
private fun EditableTrackRow(
    entry: PlaylistEntry,
    isFirst: Boolean,
    isLast: Boolean,
    onMoveUp: () -> Unit,
    onMoveDown: () -> Unit,
    onRemove: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 16.dp, end = 4.dp, top = 4.dp, bottom = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = entry.track.title,
            style = MaterialTheme.typography.bodyMedium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f)
        )
        IconButton(onClick = onMoveUp, enabled = !isFirst, modifier = Modifier.size(36.dp)) {
            Icon(
                Icons.Filled.KeyboardArrowUp,
                contentDescription = "Move up",
                modifier = Modifier.size(20.dp)
            )
        }
        IconButton(onClick = onMoveDown, enabled = !isLast, modifier = Modifier.size(36.dp)) {
            Icon(
                Icons.Filled.KeyboardArrowDown,
                contentDescription = "Move down",
                modifier = Modifier.size(20.dp)
            )
        }
        IconButton(onClick = onRemove, modifier = Modifier.size(36.dp)) {
            Icon(
                Icons.Filled.Close,
                contentDescription = "Remove from playlist",
                modifier = Modifier.size(20.dp),
                tint = MaterialTheme.colorScheme.error
            )
        }
    }
}
