package com.dresdengray.calliope.data.auth

import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthInterceptor @Inject constructor(
    private val tokenStorage: TokenStorage
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()

        // Interceptors re-run on an Authenticator-triggered retry, and TokenAuthenticator has
        // already stamped the refreshed token onto that request. Leave it alone — and use
        // header() rather than addHeader() elsewhere, because two Authorization headers arrive
        // at Starlette joined as "Bearer A, Bearer B", which fails JWT decode with a
        // permanent 401.
        if (request.header("Authorization") != null) return chain.proceed(request)

        val token = tokenStorage.accessToken ?: return chain.proceed(request)

        return chain.proceed(
            request.newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        )
    }
}
