package com.dresdengray.calliope.ui.album

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.api.model.AlbumDetail
import com.dresdengray.calliope.ui.common.UiState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class AlbumViewModel @Inject constructor(
    private val api: CalliopeApi,
    savedStateHandle: SavedStateHandle
) : ViewModel() {

    private val albumId: Int = checkNotNull(savedStateHandle["albumId"])

    private val _state = MutableStateFlow<UiState<AlbumDetail>>(UiState.Loading)
    val state: StateFlow<UiState<AlbumDetail>> = _state

    init { load() }

    fun load() {
        viewModelScope.launch {
            _state.value = UiState.Loading
            try {
                val album = api.getAlbum(albumId)
                // Enrich tracks with album/artist context so the player has everything it needs
                val enriched = album.copy(
                    tracks = album.tracks.map { track ->
                        track.copy(
                            albumId = album.id,
                            albumTitle = album.title,
                            artistId = album.artistId,
                            artistName = album.artistName
                        )
                    }
                )
                _state.value = UiState.Success(enriched)
            } catch (e: Exception) {
                _state.value = UiState.Error(e.message ?: "Failed to load album")
            }
        }
    }
}
