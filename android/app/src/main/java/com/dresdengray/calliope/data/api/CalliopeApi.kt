package com.dresdengray.calliope.data.api

import com.dresdengray.calliope.data.api.model.AlbumDetail
import com.dresdengray.calliope.data.api.model.Artist
import com.dresdengray.calliope.data.api.model.Album
import com.dresdengray.calliope.data.api.model.LoginRequest
import com.dresdengray.calliope.data.api.model.LoginResponse
import com.dresdengray.calliope.data.api.model.MeResponse
import com.dresdengray.calliope.data.api.model.RefreshRequest
import com.dresdengray.calliope.data.api.model.RefreshResponse
import com.dresdengray.calliope.data.api.model.PlayedResponse
import com.dresdengray.calliope.data.api.model.Track
import retrofit2.http.Body
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface CalliopeApi {

    // Auth — login uses OAuth2PasswordRequestForm (form-encoded), not JSON
    @FormUrlEncoded
    @POST("auth/login")
    suspend fun login(
        @Field("username") username: String,
        @Field("password") password: String
    ): LoginResponse

    @POST("auth/refresh")
    suspend fun refresh(@Body request: RefreshRequest): RefreshResponse

    @GET("auth/me")
    suspend fun me(): MeResponse

    // Library
    @GET("artists")
    suspend fun getArtists(): List<Artist>

    @GET("artists/{id}/albums")
    suspend fun getArtistAlbums(@Path("id") artistId: Int): List<Album>

    @GET("artists/{id}/top-tracks")
    suspend fun getArtistTopTracks(@Path("id") artistId: Int): List<Track>

    @GET("albums/{id}")
    suspend fun getAlbum(@Path("id") albumId: Int): AlbumDetail

    // Playback
    @POST("tracks/{id}/played")
    suspend fun reportPlayed(@Path("id") trackId: Int): PlayedResponse
}
