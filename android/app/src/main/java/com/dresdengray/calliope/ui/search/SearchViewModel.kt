package com.dresdengray.calliope.ui.search

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.api.model.SearchHistoryEntry
import com.dresdengray.calliope.data.api.model.SearchHistoryRequest
import com.dresdengray.calliope.data.api.model.SearchResults
import com.dresdengray.calliope.ui.common.UiState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@OptIn(FlowPreview::class, ExperimentalCoroutinesApi::class)
@HiltViewModel
class SearchViewModel @Inject constructor(
    private val api: CalliopeApi
) : ViewModel() {

    private val _query = MutableStateFlow("")
    val query: StateFlow<String> = _query.asStateFlow()

    /** Increments on retry to bypass StateFlow's identity-equality dedup. */
    private val _retryNonce = MutableStateFlow(0)

    private val _history = MutableStateFlow<List<SearchHistoryEntry>>(emptyList())
    val history: StateFlow<List<SearchHistoryEntry>> = _history.asStateFlow()

    /**
     * Debounced search results.
     *  - null      → no query entered
     *  - Loading   → debounced query in flight
     *  - Success   → results
     *  - Error     → API failed (use [retry] to re-issue)
     *
     * `flatMapLatest` cancels any in-flight request when a new keystroke arrives.
     */
    val results: StateFlow<UiState<SearchResults>?> =
        combine(_query, _retryNonce) { q, _ -> q }
            .debounce(300)
            .flatMapLatest { q ->
                val trimmed = q.trim()
                if (trimmed.isEmpty()) {
                    flow { emit(null) }
                } else {
                    flow {
                        emit(UiState.Loading)
                        try {
                            emit(UiState.Success(api.search(trimmed)))
                        } catch (e: Exception) {
                            emit(UiState.Error(e.message ?: "Search failed"))
                        }
                    }
                }
            }
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    init {
        refreshHistory()
    }

    fun setQuery(q: String) {
        _query.value = q
    }

    fun retry() {
        _retryNonce.value += 1
    }

    /** Fire-and-forget history record + refresh. Failures are silent (matches web). */
    fun recordHistory(entityType: String, entityId: Int) {
        viewModelScope.launch {
            try {
                api.recordSearchHistory(SearchHistoryRequest(entityType, entityId))
                refreshHistory()
            } catch (_: Exception) {
                // ignore — history is best-effort
            }
        }
    }

    private fun refreshHistory() {
        viewModelScope.launch {
            try {
                _history.value = api.getSearchHistory()
            } catch (_: Exception) {
                // ignore
            }
        }
    }
}
