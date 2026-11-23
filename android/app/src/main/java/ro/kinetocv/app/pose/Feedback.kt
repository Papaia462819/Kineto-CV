package ro.kinetocv.app.pose

import org.json.JSONObject
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.atan2

/*
 * Feedback-ul live, portat din src/feedback.py: măsurile pe cadru și motorul de reguli.
 * Regulile și pragurile vin din config/feedback.json (calibrat pe KIMORE de scripts/calibrate_feedback.py),
 * copiat în aplicație la build. Testele (LiveAnalysisTest) verifică că dă aceleași mesaje ca Python.
 */

/** Numele măsurilor, în ordinea din Python (MEASURES). */
val MEASURES = listOf(
    "shoulder", "shoulder_diff", "elbow", "tilt", "lean", "pelvis_shift", "shoulder_rotation", "pelvis_rotation",
    "wrist_height", "knee", "knee_diff", "knee_ratio",
)

private val ROTATIONS = setOf("shoulder_rotation", "pelvis_rotation")

private fun degrees(radians: Double) = radians * 180.0 / PI

/** np.fmin: dacă una din valori lipsește, o ia pe cealaltă. */
private fun fmin(a: Double, b: Double) = when {
    a.isNaN() -> b
    b.isNaN() -> a
    else -> minOf(a, b)
}

/** Măsurile pentru reguli dintr-un cadru (puncte world netezite). Unghiuri în grade, distanțe în cm. */
fun frameMeasures(world: FloatArray, mirrored: Boolean): Map<String, Double> {
    fun j(i: Int) = jointAt(world, i, mirrored)
    val shoulderL = angleAt(j(Joints.ELBOW_L), j(Joints.SHOULDER_L), j(Joints.HIP_L))
    val shoulderR = angleAt(j(Joints.ELBOW_R), j(Joints.SHOULDER_R), j(Joints.HIP_R))
    val elbowL = angleAt(j(Joints.SHOULDER_L), j(Joints.ELBOW_L), j(Joints.WRIST_L))
    val elbowR = angleAt(j(Joints.SHOULDER_R), j(Joints.ELBOW_R), j(Joints.WRIST_R))
    val kneeL = 180 - angleAt(j(Joints.HIP_L), j(Joints.KNEE_L), j(Joints.ANKLE_L))
    val kneeR = 180 - angleAt(j(Joints.HIP_R), j(Joints.KNEE_R), j(Joints.ANKLE_R))
    val shoulders = (j(Joints.SHOULDER_L) + j(Joints.SHOULDER_R)) / 2.0
    val hips = (j(Joints.HIP_L) + j(Joints.HIP_R)) / 2.0
    val ankles = (j(Joints.ANKLE_L) + j(Joints.ANKLE_R)) / 2.0
    val wrists = (j(Joints.WRIST_L) + j(Joints.WRIST_R)) / 2.0
    val trunk = shoulders - hips
    val shoulderLine = j(Joints.SHOULDER_L) - j(Joints.SHOULDER_R)
    val hipLine = j(Joints.HIP_L) - j(Joints.HIP_R)
    return mapOf(
        "shoulder" to (shoulderL + shoulderR) / 2,
        "shoulder_diff" to abs(shoulderL - shoulderR),
        "elbow" to fmin(elbowL, elbowR),
        "tilt" to degrees(atan2(trunk.x, trunk.y)),
        "lean" to degrees(atan2(-trunk.z, trunk.y)),
        "pelvis_shift" to 100 * (hips.x - ankles.x),
        "shoulder_rotation" to degrees(atan2(shoulderLine.z, shoulderLine.x)),
        "pelvis_rotation" to degrees(atan2(hipLine.z, hipLine.x)),
        "wrist_height" to 100 * (wrists.y - shoulders.y),
        "knee" to (kneeL + kneeR) / 2,
        "knee_diff" to abs(kneeL - kneeR),
        "knee_ratio" to (j(Joints.KNEE_L).x - j(Joints.KNEE_R).x) / (j(Joints.ANKLE_L).x - j(Joints.ANKLE_R).x),
    )
}

/** Unghiul principal al fiecărui exercițiu, printre măsuri (PRIMARY_MEASURE din src/session.py). */
fun primaryMeasure(exercise: Int) = when (exercise) {
    1 -> "shoulder"
    2, 4 -> "tilt"
    3 -> "shoulder_rotation"
    5 -> "knee"
    else -> error("exercițiu necunoscut: $exercise")
}

data class Rule(
    val id: String,
    val kind: String,
    val measure: String?,
    val stat: String?,
    val relative: Boolean,
    val bad: String?,
    val threshold: Double?,
    val priority: Int,
    val message: String,
    val enabled: Boolean,
)

data class FeedbackSettings(val holdS: Double, val repeatS: Double, val gapS: Double)

/** O repetare, în secunde (RepTimes din Python). */
data class RepTimes(val start: Double, val peak: Double, val end: Double, val amplitude: Double)

fun parseRule(o: JSONObject) = Rule(
    id = o.getString("id"),
    kind = o.getString("kind"),
    measure = o.optString("measure").ifEmpty { null },
    stat = o.optString("stat").ifEmpty { null },
    relative = o.optBoolean("relative", false),
    bad = o.optString("bad").ifEmpty { null },
    threshold = if (o.has("threshold") && !o.isNull("threshold")) o.getDouble("threshold") else null,
    priority = o.getInt("priority"),
    message = o.getString("message"),
    enabled = o.optBoolean("enabled", true),
)

fun parseSettings(o: JSONObject) = FeedbackSettings(o.getDouble("hold_s"), o.getDouble("repeat_s"), o.getDouble("gap_s"))

/** Regulile unui exercițiu și setările, din textul lui config/feedback.json. */
fun loadRules(json: String, exercise: Int): Pair<FeedbackSettings, List<Rule>> {
    val config = JSONObject(json)
    val rules = config.getJSONObject("exercises").getJSONArray(exercise.toString()).let { a -> List(a.length()) { parseRule(a.getJSONObject(it)) } } +
        config.getJSONArray("general").let { a -> List(a.length()) { parseRule(a.getJSONObject(it)) } }
    return parseSettings(config.getJSONObject("settings")) to rules
}

private fun median(values: List<Double>): Double {
    if (values.isEmpty()) return Double.NaN
    val sorted = values.sorted()
    val mid = sorted.size / 2
    return if (sorted.size % 2 == 1) sorted[mid] else (sorted[mid - 1] + sorted[mid]) / 2
}

/** Motorul de reguli (FeedbackEngine din src/feedback.py), aceeași logică pas cu pas. */
class FeedbackEngine(rules: List<Rule>, private val settings: FeedbackSettings) {
    private val rules = rules.filter { it.enabled }
    var baseline: Map<String, Double>? = null
        private set
    private val counts = LinkedHashMap<String, Int>()
    private val history = ArrayDeque<Pair<Double, Map<String, Double>>>()
    private val recent = HashMap<String, ArrayDeque<Boolean>>()
    private val heldSince = HashMap<String, Double>()
    private val spokenAt = HashMap<String, Double>()
    private var lastMessageT = Double.NEGATIVE_INFINITY
    private var lastRepT: Double? = null
    private val amplitudes = ArrayList<Double>()
    private val corrected = HashSet<String>()

    fun setBaseline(frames: List<Map<String, Double>>) {
        baseline = MEASURES.associateWith { m -> median(frames.mapNotNull { it[m] }.filter { it.isFinite() }) }
    }

    private fun value(rule: Rule, raw: Double): Double {
        val base = baseline
        if (!rule.relative || base == null) return raw
        var difference = raw - (base[rule.measure] ?: Double.NaN)
        if (rule.measure in ROTATIONS) difference = ((difference + 180) % 360 + 360) % 360 - 180 // ca % din Python
        return difference
    }

    /** measures = null pentru un cadru respins; rep != null când tocmai s-a încheiat o repetare. */
    fun update(t: Double, measures: Map<String, Double>?, rep: RepTimes? = null): String? {
        if (lastRepT == null) lastRepT = t
        if (measures != null) history.addLast(t to measures)
        while (history.isNotEmpty() && history.first().first < t - HISTORY_S) history.removeFirst()

        val alerts = ArrayList<Alert>()
        for (rule in rules) {
            when (rule.kind) {
                "hold" -> checkHold(rule, t, measures)?.let(alerts::add)
                "idle" -> if (t - lastRepT!! >= rule.threshold!!) {
                    alerts.add(Alert(rule))
                    lastRepT = t
                }
            }
        }
        if (rep != null) {
            lastRepT = t
            amplitudes.add(rep.amplitude)
            for (rule in rules) checkRep(rule, rep)?.let(alerts::add)
        }
        return choose(t, alerts)
    }

    private class Alert(val rule: Rule?, val message: String = rule!!.message, val priority: Int = rule!!.priority)

    private fun checkHold(rule: Rule, t: Double, measures: Map<String, Double>?): Alert? {
        if (measures == null || baseline == null) {
            heldSince.remove(rule.id)
            return null
        }
        val deviation = abs(value(rule, measures[rule.measure] ?: Double.NaN))
        if (!deviation.isFinite()) return null
        if (rule.threshold == null || deviation <= rule.threshold) {
            heldSince.remove(rule.id)
            return null
        }
        val since = heldSince.getOrPut(rule.id) { t }
        return if (t - since >= settings.holdS) Alert(rule) else null
    }

    private fun repStat(rule: Rule, rep: RepTimes): Double {
        val window = history.filter { (t, _) -> t >= rep.start && t <= rep.end }
            .mapNotNull { (t, m) -> m[rule.measure]?.takeIf { it.isFinite() }?.let { t to value(rule, it) } }
        if (window.isEmpty()) return Double.NaN
        fun at(time: Double) = window.minBy { abs(it.first - time) }.second // primul cel mai apropiat, ca np.argmin
        val values = window.map { it.second }
        return when (rule.stat) {
            "peak" -> at(rep.peak)
            "min" -> values.min()
            "max" -> values.max()
            "range" -> values.max() - values.min()
            else -> {
                if (amplitudes.size < 2) return Double.NaN // prima repetare pornește din centru
                val oneSide = at(rep.peak)
                val otherSide = -at(rep.start)
                when (rule.stat) {
                    "both_sides" -> minOf(oneSide, otherSide)
                    "sides_diff" -> abs(oneSide - otherSide)
                    else -> error("stat necunoscut: ${rule.stat}")
                }
            }
        }
    }

    private fun checkRep(rule: Rule, rep: RepTimes): Alert? {
        val wrong = when (rule.kind) {
            "rep" -> {
                val v = repStat(rule, rep)
                if (!v.isFinite() || rule.threshold == null) return null
                if (rule.bad == "low") v < rule.threshold else v > rule.threshold
            }
            "too_fast" -> rule.threshold?.let { rep.peak - rep.start < it } ?: return null
            "fatigue" -> amplitudes.size > 3 && rep.amplitude < rule.threshold!! * amplitudes.take(3).average()
            else -> return null
        }
        val last = recent.getOrPut(rule.id) { ArrayDeque() }
        last.addLast(wrong)
        if (last.size > 3) last.removeFirst()
        if (wrong) return if (last.count { it } >= 2) Alert(rule) else null
        if (rule.id in corrected && last.size >= 2 && last.takeLast(2).none { it }) {
            corrected.remove(rule.id)
            return Alert(null, GOOD_JOB, 4)
        }
        return null
    }

    private fun choose(t: Double, alerts: List<Alert>): String? {
        if (alerts.isEmpty() || t - lastMessageT < settings.gapS) return null
        val fresh = alerts.filter { t - (spokenAt[it.message] ?: Double.NEGATIVE_INFINITY) >= settings.repeatS }
        if (fresh.isEmpty()) return null
        val chosen = fresh.minBy { it.priority } // primul dintre cei cu prioritatea cea mai mare, ca min din Python
        spokenAt[chosen.message] = t
        lastMessageT = t
        chosen.rule?.let { rule ->
            counts[rule.id] = (counts[rule.id] ?: 0) + 1
            if (rule.kind == "rep") corrected.add(rule.id)
        }
        return chosen.message
    }

    /** {mesaj: de câte ori a fost spus}, de la cel mai des. */
    fun summary(): Map<String, Int> {
        val messages = rules.associate { it.id to it.message }
        return counts.entries.sortedByDescending { it.value }.associate { messages.getValue(it.key) to it.value }
    }

    companion object {
        const val GOOD_JOB = "Bine, așa!"
        const val HISTORY_S = 20.0
    }
}
