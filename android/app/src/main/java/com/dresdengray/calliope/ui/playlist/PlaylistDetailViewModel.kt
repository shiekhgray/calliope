package com.dresdengray.calliope.ui.playlist

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.api.model.PlaylistDetail
import com.dresdengray.calliope.data.api.model.ReorderRequest
import com.dresdengray.calliope.ui.common.UiState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class PlaylistDetailViewModel @Inject constructor(
    private val api: CalliopeApi,
    savedStateHandle: SavedStateHandle
) : ViewModel() {

    private val playlistId: Int = checkNotNull(savedStateHandle["playlistId"])

    private val _state = MutableStateFlow<UiState<PlaylistDetail>>(UiState.Loading)
    val state: StateFlow<UiState<PlaylistDetail>> = _state

    init { load() }

    fun load() {
        viewModelScope.launch {
            _state.value = UiState.Loading
            try {
                _state.value = UiState.Success(api.getPlaylist(playlistId))
            } catch (e: Exception) {
                _state.value = UiState.Error(e.message ?: "Failed to load playlist")
            }
        }
    }

    fun removeTrack(trackId: Int) {
        viewModelScope.launch {
            runCatching { api.removeTrackFromPlaylist(playlistId, trackId) }
            load()
        }
    }

    fun moveTrackUp(trackId: Int) {
        val entries = sortedEntries() ?: return
        val idx = entries.indexOfFirst { it.second == trackId }
        if (idx <= 0) return
        val reordered = entries.map { it.second }.toMutableList()
        reordered[idx - 1] = entries[idx].second
        reordered[idx] = entries[idx - 1].second
        reorder(reordered)
    }

    fun moveTrackDown(trackId: Int) {
        val entries = sortedEntries() ?: return
        val idx = entries.indexOfFirst { it.second == trackId }
        if (idx < 0 || idx >= entries.size - 1) return
        val reordered = entries.map { it.second }.toMutableList()
        reordered[idx + 1] = entries[idx].second
        reordered[idx] = entries[idx + 1].second
        reorder(reordered)
    }

    /** Returns list of (position, trackId) sorted by position, or null if state isn't Success. */
    private fun sortedEntries(): List<Pair<Int, Int>>? {
        val data = (_state.value as? UiState.Success)?.data ?: return null
        return data.entries
            .sortedBy { it.position }
            .map { it.position to it.track.id }
    }

    private fun reorder(trackIds: List<Int>) {
        viewModelScope.launch {
            runCatching { api.reorderPlaylistTracks(playlistId, ReorderRequest(trackIds)) }
            load()
        }
    }

    fun deletePlaylist(onDeleted: () -> Unit) {
        viewModelScope.launch {
            runCatching { api.deletePlaylist(playlistId) }
            onDeleted()
        }
    }
}
