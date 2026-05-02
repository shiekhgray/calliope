package com.dresdengray.calliope.ui.library

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.api.model.Artist
import com.dresdengray.calliope.ui.common.UiState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class LibraryViewModel @Inject constructor(
    private val api: CalliopeApi
) : ViewModel() {

    private val _state = MutableStateFlow<UiState<List<Artist>>>(UiState.Loading)
    val state: StateFlow<UiState<List<Artist>>> = _state

    init { load() }

    fun load() {
        viewModelScope.launch {
            _state.value = UiState.Loading
            try {
                _state.value = UiState.Success(api.getArtists())
            } catch (e: Exception) {
                _state.value = UiState.Error(e.message ?: "Failed to load artists")
            }
        }
    }
}
