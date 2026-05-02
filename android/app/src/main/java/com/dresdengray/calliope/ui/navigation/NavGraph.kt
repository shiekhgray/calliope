package com.dresdengray.calliope.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.dresdengray.calliope.data.auth.TokenStorage
import com.dresdengray.calliope.playback.PlayerViewModel
import com.dresdengray.calliope.ui.album.AlbumScreen
import com.dresdengray.calliope.ui.artist.ArtistScreen
import com.dresdengray.calliope.ui.auth.LoginScreen
import com.dresdengray.calliope.ui.main.MainScreen
import com.dresdengray.calliope.ui.player.NowPlayingScreen

@Composable
fun NavGraph(tokenStorage: TokenStorage, playerViewModel: PlayerViewModel) {
    val navController = rememberNavController()
    val startDestination = if (tokenStorage.isLoggedIn) "main" else "login"

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
                onOpenNowPlaying = {
                    navController.navigate("now-playing")
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
                onOpenNowPlaying = { navController.navigate("now-playing") }
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
                onOpenNowPlaying = { navController.navigate("now-playing") }
            )
        }

        composable("now-playing") {
            NowPlayingScreen(
                playerViewModel = playerViewModel,
                onNavigateBack = { navController.popBackStack() }
            )
        }
    }
}
