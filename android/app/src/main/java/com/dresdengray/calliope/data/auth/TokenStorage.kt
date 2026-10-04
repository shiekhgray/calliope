package com.dresdengray.calliope.data.auth

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.concurrent.atomic.AtomicInteger
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TokenStorage @Inject constructor(@ApplicationContext context: Context) {

    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val prefs = EncryptedSharedPreferences.create(
        context,
        "calliope_tokens",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    // Bumped by clear(). An in-flight token refresh captures the value before it starts and
    // commits only if it still matches, so a refresh that lands after Sign Out (or after a
    // failed refresh wiped the session) can't resurrect a dead session.
    private val generationCounter = AtomicInteger(0)

    private val _sessionActive = MutableStateFlow(prefs.getString(KEY_ACCESS, null) != null)

    /**
     * Observable session state. Emits `false` as soon as [clear] runs — whether that was an
     * explicit Sign Out or a failed refresh in [TokenAuthenticator] — so the UI can return to
     * the login screen instead of sitting on a screen where every request 401s.
     */
    val sessionActive: StateFlow<Boolean> = _sessionActive.asStateFlow()

    var accessToken: String?
        get() = prefs.getString(KEY_ACCESS, null)
        set(value) {
            prefs.edit().putString(KEY_ACCESS, value).apply()
            _sessionActive.value = value != null
        }

    var refreshToken: String?
        get() = prefs.getString(KEY_REFRESH, null)
        set(value) = prefs.edit().putString(KEY_REFRESH, value).apply()

    val isLoggedIn: Boolean get() = accessToken != null

    /** Opaque marker for the current session epoch; changes whenever [clear] runs. */
    val generation: Int get() = generationCounter.get()

    /**
     * Writes [token] only if the store has not been cleared since [expectedGeneration] was
     * read (see [generation]). Returns false when it has — the session is gone and the caller
     * must not bring it back.
     */
    @Synchronized
    fun commitAccessToken(token: String, expectedGeneration: Int): Boolean {
        if (generationCounter.get() != expectedGeneration) return false
        accessToken = token
        return true
    }

    @Synchronized
    fun clear() {
        generationCounter.incrementAndGet()
        prefs.edit().clear().apply()
        _sessionActive.value = false
    }

    companion object {
        private const val KEY_ACCESS = "access_token"
        private const val KEY_REFRESH = "refresh_token"
    }
}
