package ro.kinetocv.app.pose

/** Un cadru înregistrat: timpul în secunde și punctele brute (null dacă nu s-a văzut nicio persoană). */
class RecordedFrame(val t: Double, val image: FloatArray?, val world: FloatArray?)

/**
 * Păstrează punctele BRUTE, exact cum ies din MediaPipe, nu pe cele netezite live:
 * serverul face singur verificarea și netezirea, cu codul din antrenare.
 * Cadrele vin de pe firul MediaPipe, iar JSON-ul se face pe alt fir, deci metodele sunt sincronizate.
 */
class Recorder {
    private val frames = ArrayList<RecordedFrame>()
    private var startMs: Long? = null

    /** Adaugă un cadru și întoarce timpul lui față de început, în secunde (sau null dacă timpul nu a crescut). */
    @Synchronized
    fun add(timeMs: Long, image: FloatArray?, world: FloatArray?): Double? {
        val start = startMs ?: timeMs.also { startMs = it }
        val t = (timeMs - start) / 1000.0
        if (frames.isNotEmpty() && t <= frames.last().t) return null // serverul cere timpi crescători
        frames.add(RecordedFrame(t, image, world))
        return t
    }

    @get:Synchronized
    val size get() = frames.size

    @get:Synchronized
    val durationS get() = if (frames.size > 1) frames.last().t - frames.first().t else 0.0

    /**
     * Corpul cererii POST /api/patients/{id}/sessions (vezi Recording în src/api.py).
     * Scris de mână cu StringBuilder: un minut înseamnă ~500 000 de numere, iar Float.toString
     * scrie mereu cu punct zecimal (String.format ar pune virgulă pe un telefon setat în română).
     */
    @Synchronized
    fun toJson(exercise: Int, mirrored: Boolean, device: String, feedback: Map<String, Int> = emptyMap()): String {
        val out = StringBuilder(frames.size * 2400)
        out.append("{\"exercise\":").append(exercise)
            .append(",\"mirrored\":").append(mirrored)
            .append(",\"device\":\"").append(clean(device)).append("\"")
            .append(",\"feedback\":{")
            .append(feedback.entries.joinToString(",") { (message, count) -> "\"${clean(message)}\":$count" })
            .append("},\"frames\":[")
        frames.forEachIndexed { k, frame ->
            if (k > 0) out.append(',')
            out.append("{\"t\":").append(frame.t)
            val image = frame.image
            val world = frame.world
            if (image != null && world != null && image.all { it.isFinite() } && world.all { it.isFinite() }) {
                out.append(",\"image\":")
                appendArray(out, image)
                out.append(",\"world\":")
                appendArray(out, world)
            }
            out.append('}')
        }
        return out.append("]}").toString()
    }

    /** Textul pus între ghilimele în JSON: fără ghilimele, backslash sau caractere de control. */
    private fun clean(text: String) = text.filter { it != '"' && it != '\\' && it >= ' ' }

    private fun appendArray(out: StringBuilder, values: FloatArray) {
        out.append('[')
        values.forEachIndexed { i, v ->
            if (i > 0) out.append(',')
            out.append(v)
        }
        out.append(']')
    }
}
