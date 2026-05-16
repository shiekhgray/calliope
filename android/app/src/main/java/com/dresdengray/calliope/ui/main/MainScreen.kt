package com.dresdengray.calliope.ui.main

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.QueueMusic
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import com.dresdengray.calliope.playback.PlayerViewModel
import com.dresdengray.calliope.ui.player.MiniPlayerBar
import com.dresdengray.calliope.ui.playlist.PlaylistListScreen
import com.dresdengray.calliope.ui.search.SearchScreen

private data class NavTab(val label: String, val icon: ImageVector)

private val tabs = listOf(
    NavTab("Home", Icons.Filled.Home),
    NavTab("Search", Icons.Filled.Search),
    NavTab("Playlists", Icons.Filled.QueueMusic),
)

@Composable
fun MainScreen(
    playerViewModel: PlayerViewModel,
    onNavigateToArtist: (Int) -> Unit,
    onNavigateToAlbum: (Int) -> Unit,
    onNavigateToPlaylist: (Int) -> Unit,
    onLogout: () -> Unit
) {
    var selectedTab by remember { mutableIntStateOf(0) }
    val playerState by playerViewModel.uiState.collectAsState()

    // Mini-player tap switches to Home tab (index 0)
    val openNowPlaying: () -> Unit = { selectedTab = 0 }

    Scaffold(
        bottomBar = {
            Column {
                // Mini-player: shown on Search/Playlists tabs whenever a track is loaded.
                // Hidden on Home tab — the full now-playing content is already there.
                val showMiniPlayer = playerState.currentTrack != null && selectedTab != 0
                if (showMiniPlayer) {
                    MiniPlayerBar(
                        uiState = playerState,
                        onTogglePlayPause = playerViewModel::togglePlayPause,
                        onTap = openNowPlaying
                    )
                }

                NavigationBar {
                    tabs.forEachIndexed { index, tab ->
                        NavigationBarItem(
                            selected = selectedTab == index,
                            onClick = { selectedTab = index },
                            icon = { Icon(tab.icon, contentDescription = tab.label) },
                            label = { Text(tab.label) }
                        )
                    }
                }
            }
        }
    ) { padding ->
        Box(modifier = Modifier.padding(padding)) {
            when (selectedTab) {
                0 -> HomeScreen(
                    playerViewModel = playerViewModel,
                    onNavigateToArtist = onNavigateToArtist,
                    onLogout = onLogout
                )
                1 -> SearchScreen(
                    playerViewModel = playerViewModel,
                    onNavigateToArtist = onNavigateToArtist,
                    onNavigateToAlbum = onNavigateToAlbum
                )
                2 -> PlaylistListScreen(onNavigateToPlaylist = onNavigateToPlaylist)
            }
        }
    }
}
