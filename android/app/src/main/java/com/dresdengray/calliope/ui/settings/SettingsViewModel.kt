package com.dresdengray.calliope.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.api.model.ChangePasswordRequest
import com.dresdengray.calliope.data.api.model.MeResponse
import com.dresdengray.calliope.data.api.model.SimilarityWeightsRequest
import com.dresdengray.calliope.data.auth.TokenStorage
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val api: CalliopeApi,
    private val tokenStorage: TokenStorage
) : ViewModel() {

    private val _meState = MutableStateFlow<MeResponse?>(null)
    val meState: StateFlow<MeResponse?> = _meState.asStateFlow()

    init {
        loadMe()
    }

    fun loadMe() {
        viewModelScope.launch {
            runCatching { api.me() }.onSuccess { _meState.value = it }
        }
    }

    suspend fun changePassword(currentPassword: String, newPassword: String): Result<Unit> =
        runCatching {
            api.changePassword(ChangePasswordRequest(currentPassword, newPassword))
        }

    suspend fun updateSimilarityWeights(request: SimilarityWeightsRequest): Result<Unit> =
        runCatching {
            api.updateSimilarityWeights(request)
        }

    fun logout() {
        tokenStorage.clear()
    }
}
