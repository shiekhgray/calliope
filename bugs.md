# Bug Reports — Android Auto (`android/auto` branch)

**File:** `android/app/src/main/java/com/dresdengray/calliope/playback/MusicService.kt`

---

## Bug 1: Radio toggle button appears in Auto Now Playing but does nothing

**Steps to reproduce:**
1. Connect phone to car via Android Auto
2. Open Calliope in Android Auto and start playing a track from the browse tree
3. On the Now Playing card, tap the "Radio: On" command button

**Expected:** Radio mode toggles off; button label/icon updates to reflect the new state.

**Actual:** Nothing happens. The button press appears to be silently ignored.

---

## Bug 2: Duplicate tracks appended to queue when phone player is active with radio on

**Steps to reproduce:**
1. In the phone app, start playing an album or playlist with radio mode enabled
2. Let the queue run down to 1–2 remaining tracks
3. Observe the queue (in the phone UI's queue view)

**Expected:** Radio mode appends ~5 similar tracks once, driven by `PlayerViewModel`.

**Actual:** Similar tracks are appended **twice** — once by `PlayerViewModel.checkAndExtendRadioQueue()` and once by `MusicService.checkAndExtendRadioQueue()`. The service-side extension fires unconditionally on every `onMediaItemTransition` whenever `radioModeEnabled` is true, regardless of whether the playback was started from Android Auto or from the phone UI. The result is duplicate tracks in the queue.

---

# Bug Reports — Auth & Login (`android-login-fix` branch)

Numbering continues from the Android Auto section above so each bug stays
individually citable.

**Files:**
- `android/app/src/main/res/values/themes.xml`
- `android/app/src/main/java/com/dresdengray/calliope/ui/auth/LoginScreen.kt`
- `android/app/src/main/java/com/dresdengray/calliope/playback/MusicService.kt`
- `android/app/src/main/java/com/dresdengray/calliope/data/auth/TokenAuthenticator.kt`
- `android/app/src/main/java/com/dresdengray/calliope/ui/navigation/NavGraph.kt`

---

## Bug 3: Login screen renders white-on-white — title, typed text, Sign In button and errors all invisible
**Fixed:** 0f092d1 — not yet verified on device.


**Steps to reproduce:**
1. Put the phone in **dark** theme (system setting)
2. Sign out via gear icon → Sign Out
3. Observe the login screen; type into the Username and Password fields

**Expected:** A themed login screen with a visible "Calliope" title, visible
typed text, a visible "Sign In" button, and visible error messages.

**Actual:** The page is white. The title is invisible, typed characters appear
as blank space in both fields, the Sign In button does not appear at all, and
login error messages never show. The field outlines are faintly visible, which
is what makes it look like a rendering failure rather than a color problem.

**Cause:** `themes.xml:4` pins the app theme to a hardcoded **light** parent:

```xml
<style name="Theme.Calliope" parent="android:Theme.Material.Light.NoActionBar" />
```

There is no `values-night/themes.xml`, so the window background is white
regardless of system theme. Meanwhile `CalliopeTheme` keys off
`isSystemInDarkTheme()` + dynamic color and hands out **dark**-scheme content
colors (near-white `onSurface`). `MainScreen` escapes this because it has a
`Scaffold`, which paints `colorScheme.background`. `LoginScreen.kt:50` is a bare
`Column` — no `Scaffold`, no `Surface` — and `NavGraph` adds none either, so the
white window shows through under near-white text.

This single cause explains every symptom:
- Title / typed text: `onSurface` is near-white on white
- Error text: `colorScheme.error` in dynamic dark is a pale pink on white
- Sign In button: pressing Enter on the password field **submits**
  (`LoginScreen.kt` `onDone` calls `viewModel.login`), so the button is already
  in `Loading` state — a disabled M3 `Button` draws its container as
  `onSurface.copy(alpha = 0.12f)`, i.e. 12% near-white on white, with its label
  replaced by a 20dp spinner. There is genuinely nothing to see.

**Not a masking bug:** the username field already renders plain readable text,
and `PasswordVisualTransformation` (`LoginScreen.kt:82`) already masks with
bullets (`•`), not blanks. Both are *invisible*, not *blank*.

**Confirmation test:** switch the phone to light theme — the login screen should
become usable.

**Fix:**
- Add `values-night/themes.xml` with `parent="android:Theme.Material.NoActionBar"`
  (`Theme.Material` *is* the dark variant; `Theme.Material.Light` is the light one).
  Note there is **no** `android:Theme.Material.DayNight` — platform DayNight exists
  only as `android:Theme.DeviceDefault.DayNight`, added in API 29, which would
  compile against compileSdk but fail to inflate on API 26–28 (`minSdk = 26`).
  `Theme.Material3.DayNight.NoActionBar` would need a `com.google.android.material`
  dependency. The `values-night` qualifier needs no new dependency.
- Wrap `NavGraph` in `Surface(color = MaterialTheme.colorScheme.background)`
- While in `LoginScreen`: add `.imePadding()`, `.verticalScroll(rememberScrollState())`
  and `.safeDrawingPadding()` to the `Column`. With `enableEdgeToEdge()` and
  `targetSdk = 36` the IME does not resize the window, so with the keyboard
  **up** the button and error text really are behind it and there is no scroll to
  reach them. Secondary to the color bug, but real.
- Optional: a show/hide password toggle

---

## Bug 4: Playback stops ~15 minutes after the service starts — stream token is frozen at `onCreate`
**Fixed:** 0f092d1 — not yet verified on device.


**Steps to reproduce:**
1. Start playing a track (this starts `MusicService`)
2. Leave the app alone for more than 15 minutes without killing it
3. Resume or skip to another streamed (non-downloaded) track

**Expected:** Playback continues; expired access tokens are refreshed
transparently as they are on the Retrofit path.

**Actual:** Streaming fails. Downloaded tracks (`file://`) still play.

**Cause:** `MusicService.kt:385` builds a single immutable header map inside
`onCreate()`:

```kotlin
// Build a DataSource.Factory that reads the access token fresh for each stream request.
val httpDataSourceFactory = DefaultHttpDataSource.Factory().apply {
    setDefaultRequestProperties(
        mapOf("Authorization" to "Bearer ${tokenStorage.accessToken.orEmpty()}")
    )
```

The comment claims the token is read fresh per request; it is not. Access tokens
expire in 15 minutes (`api/app/config.py:9`, `access_token_expire_minutes = 15`)
and `MusicService` is a long-lived foreground service, so `onCreate` never runs
again. Every stream request for the life of the service sends the same token.

Worse, this path is `DefaultHttpDataSource`, **not** the app's `OkHttpClient`,
so it has neither `AuthInterceptor` nor `TokenAuthenticator` — there is no
refresh and no retry. The API returns 401 and ExoPlayer throws.

**Fix:** add `androidx.media3:media3-datasource-okhttp` and use
`OkHttpDataSource.Factory(okHttpClient)` with the injected authenticated client,
so streaming inherits refresh-on-401. (A `ResolvingDataSource` stamping the
header per-open also fixes the staleness but still has no retry.)

---

## Bug 5: Session death is silent — the UI never reacts, and sign-out can be undone by an in-flight refresh
**Fixed:** 0f092d1 — not yet verified on device.


**Steps to reproduce:**
1. Use the app until the session can no longer be refreshed (expired/invalid
   refresh token, or any refresh failure)
2. Try to search, list playlists, or play a track

**Expected:** The app notices the session is gone and returns to the login
screen.

**Actual:** The app stays on `MainScreen` as a zombie — search, playlists and
playback all fail silently with no indication why. The only recourse is gear →
Sign Out, or killing the app.

**Cause (two parts):**

*1 — nothing observes the token being cleared.* `TokenAuthenticator` calls
`tokenStorage.clear()` at lines 31, 36 and 47 whenever a refresh fails. After
that, `AuthInterceptor` sees `token == null` and sends requests with **no**
`Authorization` header at all, so every endpoint 401s. But
`NavGraph.kt:25` computes `startDestination` **once** at composition:

```kotlin
val startDestination = if (tokenStorage.isLoggedIn) "main" else "login"
```

and `TokenStorage` exposes plain getters rather than a `Flow`, so nothing
recomposes. A grep of the whole UI layer finds no 401 or session-expiry handling
anywhere.

*2 — sign-out can be resurrected.* `TokenAuthenticator` reads the refresh token
into a local, then writes the result back **after** the network call
(`TokenAuthenticator.kt:51`):

```kotlin
val refreshToken = tokenStorage.refreshToken ?: run { ... }
val newAccessToken = runBlocking(...) { api.get().refresh(RefreshRequest(refreshToken)) ... }
tokenStorage.accessToken = newAccessToken     // can land after tokenStorage.clear()
```

Hitting Sign Out while a refresh is in flight writes a token back *after*
logout, leaving `isLoggedIn == true` with no real session behind it.

**Fix:**
- Expose session state as a `StateFlow` from `TokenStorage`; collect it in
  `NavGraph` and navigate to `login` when it goes null
- Make the token write conditional on the store not having been cleared
  (generation counter or compare-and-set)
- Skip `authenticate()` entirely for `/auth/login` and `/auth/refresh`

---

## Bug 6: SUSPECTED — OkHttp dispatcher deadlock on a cold start with an expired access token
**Fixed:** 0f092d1 — not yet verified on device.


> **Status: theory, not confirmed.** Consistent with all observed symptoms and
> with the code as written, but not yet reproduced. The Bug 5 fix eliminates it
> either way.

**Steps to reproduce (not reliably reproducible on demand):**
1. Leave the app untouched for a few days
2. Launch it

**Expected:** Tokens refresh transparently on first use; the app works, or
returns to the login screen if the session is truly gone.

**Actual:** The app is broken on arrival. Signing out and logging back in
**does not work right away** — the login attempt appears to do nothing (no
button, no error; see Bug 3). It starts working again after "a while" (roughly
15 minutes by feel).

**Cause (hypothesis):** `TokenAuthenticator` refreshes through the **same**
`OkHttpClient` it is attached to — that is the `Lazy<CalliopeApi>` cycle the
file's own comment calls out. OkHttp's `Dispatcher` defaults to
**`maxRequestsPerHost = 5`** (`NetworkModule` does not configure one), and an
`Authenticator` runs *on the thread of the call that received the 401, while
that call still occupies its host slot*. So:

1. Five concurrent requests 401 and each hold a host slot
2. Each enters `authenticate()` and hits
   `runBlocking { api.get().refresh(...) }` — a new request to the same host,
   needing a 6th slot
3. All five slots are held by callers now blocked waiting on those refreshes;
   the refresh calls queue and never start
4. Deadlock — and **queued calls have not started, so the 15s/30s timeouts never
   begin counting**; they apply only to executing calls

Every later request, including the login POST, joins that queue and never
executes. `LoginViewModel` sits in `Loading` forever, and the button is both
disabled and invisible (Bug 3), so tapping and Enter both appear to do nothing.

The existing mitigation targets the wrong resource:

```kotlin
// Dedicated dispatcher so the refresh call doesn't compete with the OkHttp thread pool
private val refreshScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
```

`refreshScope` moves the *coroutine* dispatcher, but the scarce resource is the
OkHttp **host connection slot**, still held by the blocked call.

**Why "a few days of inactivity" is the trigger:** being away that long
guarantees both that the 15-minute access token is expired (the refresh token is
good for 30 days) *and* that the process is cold. On a cold launch
`NavGraph.kt:25` sees an access token that merely *exists* and routes straight to
`main`; `MainScreen` then composes `LibraryViewModel`, `PlaylistListViewModel`,
`SettingsViewModel.loadMe()` (fires in `init`), HomeScreen and `PlayerViewModel`,
which all issue requests **simultaneously** and all 401 at the same instant —
the thundering herd above. In normal daily use the app is warm, the token expires
mid-session, *one* request 401s, a single refresh succeeds and nothing contends.
Reproducing it requires a cold start to coincide with an already-expired access
token, which is why it arrives out of the blue.

**On the ~15 minutes:** probably not a timer — nothing client-side counts to 15.
More likely it is how long it takes Android to reclaim the backgrounded process,
after which the next launch gets a clean client.

**Ruled out by inspection:**
- No server-side lockout or rate limiting — no `limit_req`/`limit_conn` anywhere
  in `nginx/`, and `api/app/routers/auth.py` has no failed-attempt tracking
- No HTTP caching — the OkHttp client has no `.cache()`
- The login endpoint is declared correctly (`@FormUrlEncoded` + `@Field`), and
  `/auth/login` has no auth dependency, so a stale `Authorization` header cannot
  make it fail
- `secret_key` comes from `.env` and is stable across API rebuilds, so redeploys
  do not invalidate refresh tokens

**Repro / verification harness (~2 minutes):** set
`access_token_expire_minutes=1` in the API `.env` and restart the API, log in on
the phone, force-stop the app, wait ~90s, then cold-launch. This reproduces
"expired access token + cold start" directly. Revert the `.env` afterwards. Most
useful as a way to *verify the fix* — that a cold start with a dead access token
now recovers silently.

**Fix:** give the refresh path its **own** `OkHttpClient` with no authenticator
attached (breaking both the dependency cycle and the slot contention), on top of
the Bug 5 fixes.

---

## Bug 7: MINOR — `allowBackup` backs up encrypted tokens without their key
**Fixed:** 0f092d1 — not yet verified on device.


**Steps to reproduce:**
1. Back up the device and restore to a new device (or trigger a device transfer)
2. Launch Calliope

**Expected:** Either a working session or a clean login screen.

**Actual:** `EncryptedSharedPreferences` reads can throw, since the prefs file is
restored but the key that decrypts it is not.

**Cause:** `backup_rules.xml` and `data_extraction_rules.xml` are both untouched
template stubs with every rule commented out. Combined with
`android:allowBackup="true"`, `shared_prefs/calliope_tokens.xml` is backed up —
but the `MasterKey` it is encrypted with lives in the Android Keystore and is
non-exportable.

Almost certainly **not** the cause of Bug 6 (restores happen at device setup, not
after idle days), but a real latent bug.

**Fix:** add `<exclude domain="sharedpref" path="calliope_tokens.xml"/>` to both
rules files.

---

## Bug 8: A failed login invoked the token authenticator and could clear your session
**Fixed:** 0f092d1 — not yet verified on device.


**Steps to reproduce:**
1. Sign out
2. Mistype your password on the login screen

**Expected:** A "wrong credentials" error. Nothing else happens.

**Actual:** The 401 from `/auth/login` triggered `TokenAuthenticator.authenticate()`,
which burned a refresh round-trip and — if the refresh failed or no refresh token
was present — called `tokenStorage.clear()`. A typo could tear down session state.

**Cause:** `api/app/routers/auth.py` returns 401 **with `WWW-Authenticate: Bearer`**
on bad credentials:

```python
raise HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect username or password",
    headers={"WWW-Authenticate": "Bearer"},
)
```

and login goes through the *authenticated* OkHttp client, whose `Authenticator`
fires on any 401. Worse, that refresh attempt **needs a host slot on an already
saturated client** — so a failed or slow login during the Bug 6 thundering herd
would itself join the deadlock. This is the most direct explanation for
"signing out and logging back in doesn't work right away."

**Fix (applied):** `TokenAuthenticator.authenticate()` returns null immediately
for request paths ending in `/auth/login` or `/auth/refresh`, so a rejected login
surfaces as a 401 to the caller and `/auth/refresh` can never recurse.

### Correction to an earlier diagnosis

An earlier note in this investigation claimed `AuthInterceptor`'s use of
`.addHeader("Authorization", ...)` (which appends) produced **two** `Authorization`
headers on authenticator-triggered retries, yielding `Bearer A, Bearer B` and a
permanent 401. **That was mechanically wrong.** In OkHttp 4.x,
`RetryAndFollowUpInterceptor` sits *below* the application interceptors and the
authenticator's retry loop lives inside it, so interceptors registered with
`addInterceptor` do **not** re-run on a retry — only `addNetworkInterceptor` ones
do. No duplicate header was possible.

`addHeader` was still changed to `header` (plus an early pass-through when the
request already carries an `Authorization` header) because it is strictly correct
and costs nothing, but it is **hardening, not a live fix** — expect no behavior
change from it.
