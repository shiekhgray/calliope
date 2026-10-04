package com.dresdengray.calliope.ui.navigation

import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.dresdengray.calliope.data.auth.TokenStorage
import com.dresdengray.calliope.playback.PlayerViewModel
import com.dresdengray.calliope.ui.album.AlbumScreen
import com.dresdengray.calliope.ui.artist.ArtistScreen
import com.dresdengray.calliope.ui.auth.LoginScreen
import com.dresdengray.calliope.ui.main.MainScreen
import com.dresdengray.calliope.ui.playlist.PlaylistDetailScreen

@Composable
fun NavGraph(tokenStorage: TokenStorage, playerViewModel: PlayerViewModel) {
    val navController = rememberNavController()
    // Only the *initial* route is derived from stored state; after that the session flow below
    // drives us back to login if the session dies.
    val startDestination = remember { if (tokenStorage.isLoggedIn) "main" else "login" }
    val sessionActive by tokenStorage.sessionActive.collectAsState()
    val currentBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = currentBackStackEntry?.destination?.route
    val showStreamingWarning by playerViewModel.showStreamingWifiWarning.collectAsState()

    // A failed token refresh clears the store from under the UI (TokenAuthenticator), which
    // used to leave MainScreen alive as a zombie where every request 401s silently. Watch the
    // session instead of only reading it once at startup. The route guard keeps this from
    // looping and from fighting the explicit navigation in onLoginSuccess / onLogout: once we
    // are on "login" there is nothing left to do.
    LaunchedEffect(sessionActive, currentRoute) {
        if (!sessionActive && currentRoute != null && currentRoute != "login") {
            // "main" always sits below every logged-in route, so popping it inclusively clears
            // the whole stack — same idiom as onLogout below.
            navController.navigate("login") {
                popUpTo("main") { inclusive = true }
                launchSingleTop = true
            }
        }
    }

    NavHost(navController = navController, startDestination = startDestination) {

        composable("login") {
            LoginScreen(
                onLoginSuccess = {
                    navController.navigate("main") {
                        popUpTo("login") { inclusive = true }
                    }
                }
            )
        }

        composable("main") {
            MainScreen(
                playerViewModel = playerViewModel,
                onNavigateToArtist = { artistId ->
                    navController.navigate("artist/$artistId")
                },
                onNavigateToAlbum = { albumId ->
                    navController.navigate("album/$albumId")
                },
                onNavigateToPlaylist = { playlistId ->
                    navController.navigate("playlist/$playlistId")
                },
                onLogout = {
                    tokenStorage.clear()
                    navController.navigate("login") {
                        popUpTo("main") { inclusive = true }
                    }
                }
            )
        }

        composable(
            route = "artist/{artistId}",
            arguments = listOf(navArgument("artistId") { type = NavType.IntType })
        ) {
            ArtistScreen(
                playerViewModel = playerViewModel,
                onNavigateBack = { navController.popBackStack() },
                onNavigateToAlbum = { albumId -> navController.navigate("album/$albumId") },
                onOpenNowPlaying = { navController.popBackStack("main", inclusive = false) }
            )
        }

        composable(
            route = "album/{albumId}",
            arguments = listOf(navArgument("albumId") { type = NavType.IntType })
        ) {
            AlbumScreen(
                playerViewModel = playerViewModel,
                onNavigateBack = { navController.popBackStack() },
                onNavigateToArtist = { artistId ->
                    if (!navController.popBackStack("artist/$artistId", inclusive = false)) {
                        navController.navigate("artist/$artistId")
                    }
                },
                onOpenNowPlaying = { navController.popBackStack("main", inclusive = false) }
            )
        }

        composable(
            route = "playlist/{playlistId}",
            arguments = listOf(navArgument("playlistId") { type = NavType.IntType })
        ) {
            PlaylistDetailScreen(
                playerViewModel = playerViewModel,
                onNavigateBack = { navController.popBackStack() },
                onOpenNowPlaying = { navController.popBackStack("main", inclusive = false) }
            )
        }
    }

    if (showStreamingWarning) {
        AlertDialog(
            onDismissRequest = playerViewModel::dismissStreamingWarning,
            title = { Text("Mobile data") },
            text = { Text("You're on mobile data. Streaming will use your cellular data.") },
            confirmButton = {
                TextButton(onClick = playerViewModel::confirmStreamingOnCellular) {
                    Text("Stream anyway")
                }
            },
            dismissButton = {
                TextButton(onClick = playerViewModel::dismissStreamingWarning) {
                    Text("Cancel")
                }
            }
        )
    }
}
