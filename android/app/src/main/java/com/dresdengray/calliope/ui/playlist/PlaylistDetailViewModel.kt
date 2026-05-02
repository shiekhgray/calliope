package com.dresdengray.calliope.ui.playlist

import android.content.Context
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.work.ExistingWorkPolicy
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.getWorkInfosByTagFlow
import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.api.model.PlaylistDetail
import com.dresdengray.calliope.data.api.model.ReorderRequest
import com.dresdengray.calliope.data.db.DownloadStatus
import com.dresdengray.calliope.data.db.DownloadedTrackDao
import com.dresdengray.calliope.ui.common.UiState
import com.dresdengray.calliope.work.DownloadPlaylistWorker
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.io.File
import javax.inject.Inject

sealed class DownloadUiState {
    object Idle : DownloadUiState()
    data class InProgress(val done: Int, val total: Int) : DownloadUiState()
    object Complete : DownloadUiState()
}

@HiltViewModel
class PlaylistDetailViewModel @Inject constructor(
    private val api: CalliopeApi,
    private val dao: DownloadedTrackDao,
    private val workManager: WorkManager,
    @ApplicationContext private val appContext: Context,
    savedStateHandle: SavedStateHandle
) : ViewModel() {

    private val playlistId: Int = checkNotNull(savedStateHandle["playlistId"])

    private val _state = MutableStateFlow<UiState<PlaylistDetail>>(UiState.Loading)
    val state: StateFlow<UiState<PlaylistDetail>> = _state

    /** IDs of tracks with a DONE download entry for this playlist. */
    val downloadedTrackIds: StateFlow<Set<Int>> = dao
        .observeByPlaylist(playlistId.toLong())
        .map { list ->
            list.filter { it.status == DownloadStatus.DONE }
                .map { it.trackId.toInt() }
                .toSet()
        }
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptySet())

    val downloadUiState: StateFlow<DownloadUiState> = combine(
        _state,
        dao.observeByPlaylist(playlistId.toLong()),
        workManager.getWorkInfosByTagFlow("${DownloadPlaylistWorker.TAG_PREFIX}$playlistId")
    ) { playlistState, downloaded, workInfos ->
        val total = (playlistState as? UiState.Success)?.data?.entries?.size ?: 0
        val doneCount = downloaded.count { it.status == DownloadStatus.DONE }
        val isActive = workInfos.any {
            it.state == WorkInfo.State.ENQUEUED || it.state == WorkInfo.State.RUNNING
        }
        when {
            isActive -> DownloadUiState.InProgress(doneCount, total)
            total > 0 && doneCount >= total -> DownloadUiState.Complete
            else -> DownloadUiState.Idle
        }
    }.stateIn(viewModelScope, SharingStarted.Eagerly, DownloadUiState.Idle)

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

    fun startDownload() {
        val request = DownloadPlaylistWorker.buildRequest(playlistId.toLong())
        workManager.enqueueUniqueWork(
            "download_playlist_$playlistId",
            ExistingWorkPolicy.KEEP,
            request
        )
    }

    fun cancelDownload() {
        workManager.cancelAllWorkByTag("${DownloadPlaylistWorker.TAG_PREFIX}$playlistId")
        viewModelScope.launch {
            val entries = dao.observeByPlaylist(playlistId.toLong()).first()
            entries.forEach { track ->
                if (track.filePath.isNotEmpty()) File(track.filePath).delete()
            }
            dao.deleteByPlaylist(playlistId.toLong())
            // Also remove the playlist directory if empty
            File(appContext.filesDir, "playlists/$playlistId").delete()
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
