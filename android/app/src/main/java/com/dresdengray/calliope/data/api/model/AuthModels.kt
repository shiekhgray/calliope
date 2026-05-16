package com.dresdengray.calliope.data.api.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class LoginRequest(val username: String, val password: String)

@JsonClass(generateAdapter = true)
data class LoginResponse(
    @Json(name = "access_token") val accessToken: String,
    @Json(name = "refresh_token") val refreshToken: String,
    @Json(name = "token_type") val tokenType: String = "bearer"
)

@JsonClass(generateAdapter = true)
data class RefreshRequest(
    @Json(name = "refresh_token") val refreshToken: String
)

@JsonClass(generateAdapter = true)
data class RefreshResponse(
    @Json(name = "access_token") val accessToken: String,
    @Json(name = "token_type") val tokenType: String = "bearer"
)

@JsonClass(generateAdapter = true)
data class MeResponse(
    val id: Int,
    val username: String,
    @Json(name = "sim_weight_timbre") val simWeightTimbre: Int = 5,
    @Json(name = "sim_weight_timbral_variation") val simWeightTimbralVariation: Int = 5,
    @Json(name = "sim_weight_harmony") val simWeightHarmony: Int = 5,
    @Json(name = "sim_weight_chord_movement") val simWeightChordMovement: Int = 5,
    @Json(name = "sim_weight_tempo") val simWeightTempo: Int = 5,
    @Json(name = "sim_weight_loudness") val simWeightLoudness: Int = 5,
    @Json(name = "sim_weight_dynamic_range") val simWeightDynamicRange: Int = 5,
    @Json(name = "sim_weight_brightness") val simWeightBrightness: Int = 5,
    @Json(name = "sim_weight_tonal") val simWeightTonal: Int = 5
)

@JsonClass(generateAdapter = true)
data class ChangePasswordRequest(
    @Json(name = "current_password") val currentPassword: String,
    @Json(name = "new_password") val newPassword: String
)

@JsonClass(generateAdapter = true)
data class SimilarityWeightsRequest(
    @Json(name = "sim_weight_timbre") val simWeightTimbre: Int,
    @Json(name = "sim_weight_timbral_variation") val simWeightTimbralVariation: Int,
    @Json(name = "sim_weight_harmony") val simWeightHarmony: Int,
    @Json(name = "sim_weight_chord_movement") val simWeightChordMovement: Int,
    @Json(name = "sim_weight_tempo") val simWeightTempo: Int,
    @Json(name = "sim_weight_loudness") val simWeightLoudness: Int,
    @Json(name = "sim_weight_dynamic_range") val simWeightDynamicRange: Int,
    @Json(name = "sim_weight_brightness") val simWeightBrightness: Int,
    @Json(name = "sim_weight_tonal") val simWeightTonal: Int
)
