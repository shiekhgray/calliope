package com.dresdengray.calliope.data.auth

import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.api.model.MeResponse
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val api: CalliopeApi,
    private val tokenStorage: TokenStorage
) {
    val isLoggedIn: Boolean get() = tokenStorage.isLoggedIn

    suspend fun login(username: String, password: String) {
        val response = api.login(username, password)
        tokenStorage.accessToken = response.accessToken
        tokenStorage.refreshToken = response.refreshToken
    }

    suspend fun me(): MeResponse = api.me()

    fun logout() = tokenStorage.clear()
}
