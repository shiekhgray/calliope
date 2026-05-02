package com.dresdengray.calliope.ui.artist

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.api.model.Album
import com.dresdengray.calliope.data.api.model.Track
import com.dresdengray.calliope.ui.common.UiState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ArtistUiData(
    val artistName: String,
    val albums: List<Album>,
    val topTracks: List<Track>
)

@HiltViewModel
class ArtistViewModel @Inject constructor(
    private val api: CalliopeApi,
    savedStateHandle: SavedStateHandle
) : ViewModel() {

    private val artistId: Int = checkNotNull(savedStateHandle["artistId"])

    private val _state = MutableStateFlow<UiState<ArtistUiData>>(UiState.Loading)
    val state: StateFlow<UiState<ArtistUiData>> = _state

    init { load() }

    fun load() {
        viewModelScope.launch {
            _state.value = UiState.Loading
            try {
                coroutineScope {
                    val albumsDeferred = async { api.getArtistAlbums(artistId) }
                    val topTracksDeferred = async { api.getArtistTopTracks(artistId) }
                    val albums = albumsDeferred.await()
                    val topTracks = topTracksDeferred.await()
                    val artistName = albums.firstOrNull()?.artistName
                        ?: topTracks.firstOrNull()?.artistName
                        ?: ""
                    _state.value = UiState.Success(ArtistUiData(artistName, albums, topTracks))
                }
            } catch (e: Exception) {
                _state.value = UiState.Error(e.message ?: "Failed to load artist")
            }
        }
    }
}
