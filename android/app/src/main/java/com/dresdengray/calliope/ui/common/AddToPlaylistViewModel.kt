package com.dresdengray.calliope.ui.common

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.api.model.AddTrackRequest
import com.dresdengray.calliope.data.api.model.Playlist
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class AddToPlaylistViewModel @Inject constructor(
    private val api: CalliopeApi
) : ViewModel() {

    private val _playlists = MutableStateFlow<List<Playlist>>(emptyList())
    val playlists: StateFlow<List<Playlist>> = _playlists.asStateFlow()

    fun fetchPlaylists() {
        viewModelScope.launch {
            runCatching { _playlists.value = api.getPlaylists() }
        }
    }

    suspend fun addTrack(playlistId: Int, trackId: Int) {
        api.addTrackToPlaylist(playlistId, AddTrackRequest(trackId))
    }
}
