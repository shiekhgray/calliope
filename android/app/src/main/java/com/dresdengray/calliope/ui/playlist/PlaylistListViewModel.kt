package com.dresdengray.calliope.ui.playlist

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.api.model.CreatePlaylistRequest
import com.dresdengray.calliope.data.api.model.Playlist
import com.dresdengray.calliope.ui.common.UiState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class PlaylistListViewModel @Inject constructor(
    private val api: CalliopeApi
) : ViewModel() {

    private val _state = MutableStateFlow<UiState<List<Playlist>>>(UiState.Loading)
    val state: StateFlow<UiState<List<Playlist>>> = _state

    init { load() }

    fun load() {
        viewModelScope.launch {
            _state.value = UiState.Loading
            try {
                _state.value = UiState.Success(api.getPlaylists())
            } catch (e: Exception) {
                _state.value = UiState.Error(e.message ?: "Failed to load playlists")
            }
        }
    }

    fun createPlaylist(title: String, description: String?) {
        viewModelScope.launch {
            runCatching {
                api.createPlaylist(
                    CreatePlaylistRequest(
                        title = title,
                        description = description?.takeIf { it.isNotBlank() }
                    )
                )
            }
            load()
        }
    }

    fun deletePlaylist(playlistId: Int) {
        viewModelScope.launch {
            runCatching { api.deletePlaylist(playlistId) }
            load()
        }
    }
}
