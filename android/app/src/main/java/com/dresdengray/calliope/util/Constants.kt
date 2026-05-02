package com.dresdengray.calliope.util

object Constants {
    const val BASE_URL = "https://dresdengray.com/calliope/api/"

    fun albumArtUrl(albumId: Int) = "${BASE_URL}albums/$albumId/art"
    fun streamUrl(trackId: Int) = "${BASE_URL}tracks/$trackId/stream"
}
