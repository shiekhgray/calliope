package com.dresdengray.calliope.data.auth

import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.api.model.RefreshRequest
import dagger.Lazy
import kotlinx.coroutines.runBlocking
import okhttp3.Authenticator
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TokenAuthenticator @Inject constructor(
    private val tokenStorage: TokenStorage,
    // Lazy breaks the circular dependency: OkHttpClient → Authenticator → Api → Retrofit → OkHttpClient
    private val api: Lazy<CalliopeApi>
) : Authenticator {

    override fun authenticate(route: Route?, response: Response): Request? {
        // If this request already carried a freshly-refreshed token, give up to avoid loops
        if (response.request.header("X-Token-Refreshed") != null) {
            tokenStorage.clear()
            return null
        }

        val refreshToken = tokenStorage.refreshToken ?: run {
            tokenStorage.clear()
            return null
        }

        val newAccessToken = runBlocking {
            try {
                api.get().refresh(RefreshRequest(refreshToken)).accessToken
            } catch (e: Exception) {
                null
            }
        } ?: run {
            tokenStorage.clear()
            return null
        }

        tokenStorage.accessToken = newAccessToken

        return response.request.newBuilder()
            .header("Authorization", "Bearer $newAccessToken")
            .header("X-Token-Refreshed", "true")
            .build()
    }
}
