package com.dresdengray.calliope.di

import com.dresdengray.calliope.BuildConfig
import com.dresdengray.calliope.data.api.CalliopeApi
import com.dresdengray.calliope.data.auth.AuthInterceptor
import com.dresdengray.calliope.data.auth.TokenAuthenticator
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import com.dresdengray.calliope.util.Constants
import dagger.hilt.components.SingletonComponent
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Qualifier
import javax.inject.Singleton

/**
 * Marks the stripped-down OkHttpClient / Retrofit / CalliopeApi used *only* by
 * [TokenAuthenticator] to call `POST /auth/refresh`. It carries no [AuthInterceptor] and no
 * authenticator, which matters twice over:
 *
 *  1. It breaks the `OkHttpClient -> Authenticator -> Api -> Retrofit -> OkHttpClient`
 *     dependency cycle that previously needed a `dagger.Lazy` to work around.
 *  2. It keeps the refresh call off the authenticated client's Dispatcher. OkHttp allows
 *     `maxRequestsPerHost = 5` and runs an Authenticator on the thread of the 401'd call
 *     *while that call still holds its host slot*, so refreshing through the same client
 *     lets 5 simultaneous 401s (exactly what a cold start with an expired access token
 *     produces) deadlock the client permanently — queued calls never start, so their
 *     timeouts never begin counting either.
 */
@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class RefreshClient

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    private val BASE_URL get() = Constants.BASE_URL

    @Provides @Singleton
    fun provideMoshi(): Moshi = Moshi.Builder()
        .addLast(KotlinJsonAdapterFactory())
        .build()

    @Provides @Singleton
    fun provideOkHttpClient(
        authInterceptor: AuthInterceptor,
        tokenAuthenticator: TokenAuthenticator
    ): OkHttpClient = OkHttpClient.Builder()
        .addInterceptor(authInterceptor)
        .authenticator(tokenAuthenticator)
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .apply { loggingInterceptor()?.let { logger -> addInterceptor(logger) } }
        .build()

    @Provides @Singleton @RefreshClient
    fun provideRefreshOkHttpClient(): OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .apply { loggingInterceptor()?.let { logger -> addInterceptor(logger) } }
        .build()

    @Provides @Singleton
    fun provideRetrofit(okHttpClient: OkHttpClient, moshi: Moshi): Retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(MoshiConverterFactory.create(moshi))
        .build()

    @Provides @Singleton @RefreshClient
    fun provideRefreshRetrofit(
        @RefreshClient okHttpClient: OkHttpClient,
        moshi: Moshi
    ): Retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(MoshiConverterFactory.create(moshi))
        .build()

    @Provides @Singleton
    fun provideCalliopeApi(retrofit: Retrofit): CalliopeApi =
        retrofit.create(CalliopeApi::class.java)

    @Provides @Singleton @RefreshClient
    fun provideRefreshApi(@RefreshClient retrofit: Retrofit): CalliopeApi =
        retrofit.create(CalliopeApi::class.java)

    /**
     * Debug-only HTTP logging — at BODY level it would otherwise dump bearer tokens and full
     * JSON payloads into release logcat. Returns null in release builds.
     *
     * Audio streaming is exempted: BODY logging calls `source.request(Long.MAX_VALUE)`, i.e.
     * it buffers the *entire* response body before handing it on, which would stall playback
     * and balloon memory now that ExoPlayer streams through this same client.
     */
    private fun loggingInterceptor(): Interceptor? {
        if (!BuildConfig.DEBUG) return null
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }
        return Interceptor { chain ->
            val request = chain.request()
            if (request.url.encodedPath.endsWith("/stream")) chain.proceed(request)
            else logging.intercept(chain)
        }
    }
}
