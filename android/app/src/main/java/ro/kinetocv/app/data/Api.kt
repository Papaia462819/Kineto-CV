package ro.kinetocv.app.data

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

data class PlanItem(val exercise: Int, val reps: Int, val perWeek: Int)

data class Patient(
    val id: Int, val name: String, val birthYear: Int?, val diagnosis: String?, val therapist: String?, val plan: List<PlanItem>,
)

data class Session(
    val id: Int,
    val created: String,
    val exercise: Int,
    val durationS: Double?,
    val kept: Double?,
    val reps: Int?,
    val romMean: Double?,
    val romFatigue: Double?,
    val score: Double?,
    val scoreError: Double?,
    val looksLike: Int?,
    val warnings: List<String>,
    val feedback: Map<String, Int>, // mesajele de corectare spuse live, cu de câte ori
    val reviewText: String?,
    val reviewAuthor: String?,
    val reviewCreated: String?,
)

data class Message(val id: Int, val created: String, val authorRole: String, val authorName: String, val text: String)

class ApiException(message: String) : Exception(message)

/** Adresa serverului și pacientul, păstrate pe telefon. */
class Settings(context: Context) {
    private val prefs = context.getSharedPreferences("kineto", Context.MODE_PRIVATE)

    var serverUrl: String
        get() = prefs.getString("server_url", DEFAULT_SERVER) ?: DEFAULT_SERVER
        set(value) = prefs.edit().putString("server_url", value.trim().trimEnd('/')).apply()

    var patientId: Int
        get() = prefs.getInt("patient_id", 1)
        set(value) = prefs.edit().putInt("patient_id", value).apply()

    companion object {
        // Adresa laptopului în rețeaua de acasă; scripts/run_server.py o afișează la pornire.
        const val DEFAULT_SERVER = "http://192.168.1.128:8000"
    }
}

/** Vorbește cu serverul Python (src/api.py). Toate funcțiile rulează pe firul de rețea (Dispatchers.IO). */
class Api(private val settings: Settings) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    private val base get() = settings.serverUrl
    private val patient get() = settings.patientId

    private suspend fun call(request: Request): String = withContext(Dispatchers.IO) {
        client.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val detail = runCatching { JSONObject(body).opt("detail")?.toString() }.getOrNull() ?: body.take(200)
                throw ApiException("Serverul a răspuns ${response.code}: $detail")
            }
            body
        }
    }

    private suspend fun get(path: String) = call(Request.Builder().url(base + path).build())

    private suspend fun post(path: String, json: String) =
        call(Request.Builder().url(base + path).post(json.toRequestBody("application/json".toMediaType())).build())

    suspend fun health(): Double = JSONObject(get("/api/health")).getDouble("score_error")

    suspend fun patient(): Patient {
        val o = JSONObject(get("/api/patients/$patient"))
        val plan = o.getJSONArray("plan").objects().map { PlanItem(it.getInt("exercise"), it.getInt("reps"), it.getInt("per_week")) }
        return Patient(o.getInt("id"), o.getString("name"), o.intOrNull("birth_year"), o.stringOrNull("diagnosis"),
            o.stringOrNull("therapist"), plan)
    }

    suspend fun sessions(): List<Session> = JSONArray(get("/api/patients/$patient/sessions")).objects().map(::session)

    suspend fun session(id: Int): Session = session(JSONObject(get("/api/sessions/$id")))

    /** Trimite o înregistrare (JSON-ul din Recorder) și primește sesiunea analizată. */
    suspend fun upload(recordingJson: String): Session = session(JSONObject(post("/api/patients/$patient/sessions", recordingJson)))

    suspend fun messages(): List<Message> = JSONArray(get("/api/patients/$patient/messages")).objects().map(::message)

    suspend fun sendMessage(authorName: String, text: String): List<Message> {
        val body = JSONObject().put("author_role", "patient").put("author_name", authorName).put("text", text).toString()
        return JSONArray(post("/api/patients/$patient/messages", body)).objects().map(::message)
    }

    private fun session(o: JSONObject) = Session(
        id = o.getInt("id"),
        created = o.getString("created"),
        exercise = o.getInt("exercise"),
        durationS = o.doubleOrNull("duration_s"),
        kept = o.doubleOrNull("kept"),
        reps = o.intOrNull("reps"),
        romMean = o.doubleOrNull("rom_mean"),
        romFatigue = o.doubleOrNull("rom_fatigue"),
        score = o.doubleOrNull("score"),
        scoreError = o.doubleOrNull("score_error"),
        looksLike = o.intOrNull("looks_like"),
        warnings = o.optJSONArray("warnings")?.let { a -> List(a.length()) { a.getString(it) } } ?: emptyList(),
        feedback = o.optJSONObject("feedback")?.let { f -> f.keys().asSequence().associateWith { f.getInt(it) } } ?: emptyMap(),
        reviewText = o.stringOrNull("review_text"),
        reviewAuthor = o.stringOrNull("review_author"),
        reviewCreated = o.stringOrNull("review_created"),
    )

    private fun message(o: JSONObject) =
        Message(o.getInt("id"), o.getString("created"), o.getString("author_role"), o.getString("author_name"), o.getString("text"))
}

// org.json întoarce "null" ca text pentru valorile lipsă; ajutoarele de mai jos dau null adevărat.
private fun JSONObject.stringOrNull(key: String) = if (isNull(key)) null else getString(key)
private fun JSONObject.doubleOrNull(key: String) = if (isNull(key)) null else getDouble(key)
private fun JSONObject.intOrNull(key: String) = if (isNull(key)) null else getInt(key)
private fun JSONArray.objects() = List(length()) { getJSONObject(it) }

/** Un mesaj de eroare pe înțelesul utilizatorului. */
fun Throwable.userMessage(): String = when (this) {
    is ApiException -> message ?: "Eroare de server"
    is IOException -> "Nu pot contacta serverul. Verifică adresa din Setări și că telefonul e în aceeași rețea Wi-Fi cu laptopul."
    else -> message ?: toString()
}
