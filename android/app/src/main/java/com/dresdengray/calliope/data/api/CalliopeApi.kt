package com.dresdengray.calliope.data.api

import com.dresdengray.calliope.data.api.model.AddTrackRequest
import com.dresdengray.calliope.data.api.model.AlbumDetail
import com.dresdengray.calliope.data.api.model.Artist
import com.dresdengray.calliope.data.api.model.Album
import com.dresdengray.calliope.data.api.model.ChangePasswordRequest
import com.dresdengray.calliope.data.api.model.CreatePlaylistRequest
import com.dresdengray.calliope.data.api.model.LoginRequest
import com.dresdengray.calliope.data.api.model.LoginResponse
import com.dresdengray.calliope.data.api.model.MeResponse
import com.dresdengray.calliope.data.api.model.Playlist
import com.dresdengray.calliope.data.api.model.PlaylistDetail
import com.dresdengray.calliope.data.api.model.RefreshRequest
import com.dresdengray.calliope.data.api.model.RefreshResponse
import com.dresdengray.calliope.data.api.model.PlayedResponse
import com.dresdengray.calliope.data.api.model.ReorderRequest
import com.dresdengray.calliope.data.api.model.SearchHistoryEntry
import com.dresdengray.calliope.data.api.model.SearchHistoryRequest
import com.dresdengray.calliope.data.api.model.SearchResults
import com.dresdengray.calliope.data.api.model.SimilarityWeightsRequest
import com.dresdengray.calliope.data.api.model.Track
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

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

    @POST("auth/change-password")
    suspend fun changePassword(@Body request: ChangePasswordRequest)

    @PUT("auth/similarity-weights")
    suspend fun updateSimilarityWeights(@Body request: SimilarityWeightsRequest)

    // Library
    @GET("artists")
    suspend fun getArtists(): List<Artist>

    @GET("artists/{id}/albums")
    suspend fun getArtistAlbums(@Path("id") artistId: Int): List<Album>

    // Singles & EPs for this artist (album_type IN ('single', 'ep'))
    @GET("artists/{id}/singles")
    suspend fun getArtistSingles(@Path("id") artistId: Int): List<Album>

    // Albums where artist has a track credit but is not the primary album artist
    @GET("artists/{id}/compilations")
    suspend fun getArtistCompilations(@Path("id") artistId: Int): List<Album>

    @GET("artists/{id}/top-tracks")
    suspend fun getArtistTopTracks(@Path("id") artistId: Int): List<Track>

    @GET("albums/{id}")
    suspend fun getAlbum(@Path("id") albumId: Int): AlbumDetail

    // Tracks
    @GET("tracks")
    suspend fun getTopTracks(
        @Query("sort") sort: String = "play_count",
        @Query("limit") limit: Int = 50
    ): List<Track>

    @POST("tracks/{id}/played")
    suspend fun reportPlayed(@Path("id") trackId: Int): PlayedResponse

    @GET("tracks/{id}/similar")
    suspend fun getSimilarTracks(
        @Path("id") trackId: Int,
        @Query("limit") limit: Int = 5
    ): List<Track>

    // Search
    @GET("search")
    suspend fun search(@Query("q") q: String): SearchResults

    @GET("search/history")
    suspend fun getSearchHistory(): List<SearchHistoryEntry>

    @POST("search/history")
    suspend fun recordSearchHistory(@Body body: SearchHistoryRequest)

    // Playlists
    @GET("playlists")
    suspend fun getPlaylists(): List<Playlist>

    @GET("playlists/{id}")
    suspend fun getPlaylist(@Path("id") id: Int): PlaylistDetail

    @POST("playlists")
    suspend fun createPlaylist(@Body body: CreatePlaylistRequest): Playlist

    @DELETE("playlists/{id}")
    suspend fun deletePlaylist(@Path("id") id: Int)

    @POST("playlists/{id}/tracks")
    suspend fun addTrackToPlaylist(@Path("id") playlistId: Int, @Body body: AddTrackRequest)

    @DELETE("playlists/{id}/tracks/{trackId}")
    suspend fun removeTrackFromPlaylist(
        @Path("id") playlistId: Int,
        @Path("trackId") trackId: Int
    )

    @PUT("playlists/{id}/tracks/reorder")
    suspend fun reorderPlaylistTracks(@Path("id") playlistId: Int, @Body body: ReorderRequest)

    @GET("playlists/{id}/similar")
    suspend fun getPlaylistSimilar(
        @Path("id") playlistId: Int,
        @Query("limit") limit: Int = 10
    ): List<Track>
}
