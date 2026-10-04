package com.dresdengray.calliope.data.auth

import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.api.model.RefreshRequest
import com.dresdengray.calliope.di.RefreshClient
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
    // @RefreshClient is a separate, unauthenticated OkHttpClient/Retrofit pair. Refreshing
    // through the client this Authenticator is attached to deadlocks that client: authenticate()
    // runs on the thread of the 401'd call while that call still holds one of OkHttp's 5
    // per-host slots, so five simultaneous 401s leave no slot for any refresh to run in.
    @RefreshClient private val api: CalliopeApi
) : Authenticator {

    override fun authenticate(route: Route?, response: Response): Request? {
        // Never refresh on behalf of an auth call. A rejected login must surface as a 401 to
        // the caller, not clear the stored session, and /auth/refresh must never recurse.
        val path = response.request.url.encodedPath
        if (path.endsWith("/auth/login") || path.endsWith("/auth/refresh")) return null

        // If this request already carried a freshly-refreshed token, give up to avoid loops
        if (response.request.header("X-Token-Refreshed") != null) {
            tokenStorage.clear()
            return null
        }

        // Capture the session epoch before the network call so the write below can tell
        // whether the session was signed out while the refresh was in flight.
        val generation = tokenStorage.generation

        val refreshToken = tokenStorage.refreshToken ?: run {
            tokenStorage.clear()
            return null
        }

        // runBlocking is required: Authenticator.authenticate() is a blocking contract that has
        // to return the Request to retry. It is safe here because the refresh runs on its own
        // client — it is not waiting on a connection slot held by this very thread.
        val newAccessToken = runBlocking {
            try {
                api.refresh(RefreshRequest(refreshToken)).accessToken
            } catch (e: Exception) {
                null
            }
        } ?: run {
            tokenStorage.clear()
            return null
        }

        // Don't resurrect a session that died while we were refreshing (Sign Out, or another
        // thread's failed refresh calling clear()).
        if (!tokenStorage.commitAccessToken(newAccessToken, generation)) return null

        return response.request.newBuilder()
            .header("Authorization", "Bearer $newAccessToken")
            .header("X-Token-Refreshed", "true")
            .build()
    }
}
