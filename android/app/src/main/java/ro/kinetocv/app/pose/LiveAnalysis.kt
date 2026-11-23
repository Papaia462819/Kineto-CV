package ro.kinetocv.app.pose

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.acos
import kotlin.math.atan2
import kotlin.math.sqrt

/*
 * Partea live, portată din Python (src/features.py, src/filters.py, src/reps.py, src/quality.py).
 * Servește doar ce vede persoana în timpul exercițiului: repetările și mesajele despre poziție.
 * Scorul NU se calculează aici: la final, punctele brute merg la server, care rulează codul din antrenare.
 * De aceea mici diferențe față de Python nu strică nimic (cel mult numărătoarea live diferă cu o repetare).
 */

/** Indicii MediaPipe ai punctelor folosite (aceiași ca în src/features.py). */
object Joints {
    const val SHOULDER_L = 11
    const val SHOULDER_R = 12
    const val ELBOW_L = 13
    const val ELBOW_R = 14
    const val WRIST_L = 15
    const val WRIST_R = 16
    const val HIP_L = 23
    const val HIP_R = 24
    const val KNEE_L = 25
    const val KNEE_R = 26
    const val ANKLE_L = 27
    const val ANKLE_R = 28
    val CORE = intArrayOf(SHOULDER_L, SHOULDER_R, HIP_L, HIP_R)
    const val VALUES = 33 * 4 // 33 de puncte × (x, y, z, vizibilitate)
}

/** Exercițiile KIMORE, cu unghiul din care se numără repetările (PRIMARY_ANGLE și REP_PROMINENCE din Python). */
data class Exercise(val id: Int, val name: String, val description: String, val angleLabel: String, val prominence: Double)

object Exercises {
    val all = listOf(
        Exercise(1, "Ridicarea brațelor", "Brațele întinse urcă prin față deasupra capului și coboară.", "umeri", 25.0),
        Exercise(2, "Înclinări laterale", "Cu brațele sus, trunchiul se înclină spre stânga și spre dreapta.", "înclinarea trunchiului", 8.0),
        Exercise(3, "Rotația trunchiului", "Cu bastonul ținut în față, la nivelul umerilor, trunchiul se rotește stânga-dreapta.", "rotația umerilor", 30.0),
        Exercise(4, "Rotația pelvisului", "Cu mâinile pe șolduri, pelvisul se rotește în plan orizontal.", "înclinarea trunchiului", 5.0),
        Exercise(5, "Genuflexiuni", "Cu bastonul ținut în față, cobori în genuflexiune și urci.", "flexia genunchilor", 15.0),
    )

    fun byId(id: Int) = all.first { it.id == id }
}

internal data class V(val x: Double, val y: Double, val z: Double) {
    operator fun plus(o: V) = V(x + o.x, y + o.y, z + o.z)
    operator fun minus(o: V) = V(x - o.x, y - o.y, z - o.z)
    operator fun div(k: Double) = V(x / k, y / k, z / k)
    infix fun dot(o: V) = x * o.x + y * o.y + z * o.z
    fun norm() = sqrt(this dot this)
}

private fun degrees(radians: Double) = radians * 180.0 / PI

/** Punctul i în axele comune: x spre stânga persoanei, y în sus, z dinspre cameră (named_joints din Python). */
internal fun jointAt(world: FloatArray, i: Int, mirrored: Boolean): V {
    val sx = if (mirrored) -1.0 else 1.0
    return V(sx * world[i * 4], -world[i * 4 + 1].toDouble(), world[i * 4 + 2].toDouble())
}

/** Unghiul în b, între b→a și b→c, în grade (angle_at din Python). */
internal fun angleAt(a: V, b: V, c: V): Double {
    val v1 = a - b
    val v2 = c - b
    val cosine = (v1 dot v2) / (v1.norm() * v2.norm())
    return degrees(acos(cosine.coerceIn(-1.0, 1.0)))
}

/** Unghiul principal al exercițiului, din punctele în metri ale unui cadru (compute_angles din Python). */
fun primaryAngle(exercise: Int, world: FloatArray, mirrored: Boolean): Double =
    frameMeasures(world, mirrored).getValue(primaryMeasure(exercise))

/** Starea unui cadru: o versiune simplificată a QualityChecker din Python (serverul face verificarea completă). */
enum class FrameStatus(val message: String) {
    OK(""),
    MISSING("Nu te văd: intră în cadru"),
    LOW_VISIBILITY("Nu te văd întreg: depărtează-te de cameră"),
    UPSIDE_DOWN("Detecție nesigură: stai drept, cu fața la cameră"),
}

fun judgeFrame(image: FloatArray?, world: FloatArray?): FrameStatus {
    if (image == null || world == null) return FrameStatus.MISSING
    if (Joints.CORE.any { i -> (0..2).any { !world[i * 4 + it].isFinite() } }) return FrameStatus.MISSING
    if (Joints.CORE.minOf { world[it * 4 + 3] } < 0.5f) return FrameStatus.LOW_VISIBILITY
    val shoulders = (image[Joints.SHOULDER_L * 4 + 1] + image[Joints.SHOULDER_R * 4 + 1]) / 2
    val hips = (image[Joints.HIP_L * 4 + 1] + image[Joints.HIP_R * 4 + 1]) / 2
    if (shoulders >= hips) return FrameStatus.UPSIDE_DOWN // y crește în jos în imagine
    return FrameStatus.OK
}

/** Filtrul One Euro (src/filters.py): netezește mult când punctul stă și puțin când se mișcă repede. */
class OneEuroFilter(private val minCutoff: Double = 1.0, private val beta: Double = 0.5, private val dCutoff: Double = 1.0) {
    private var x: DoubleArray? = null
    private var dx: DoubleArray? = null
    private var t = 0.0

    fun reset() {
        x = null
    }

    private fun alpha(cutoff: Double, dt: Double) = 1.0 / (1.0 + 1.0 / (2.0 * PI * cutoff * dt))

    fun filter(value: DoubleArray, time: Double): DoubleArray {
        val previous = x
        val dt = time - t
        if (previous == null || dt <= 0) {
            x = value.copyOf()
            dx = DoubleArray(value.size)
            t = time
            return value.copyOf()
        }
        val speed = dx!!
        val aD = alpha(dCutoff, dt)
        val result = DoubleArray(value.size) { i ->
            speed[i] += aD * ((value[i] - previous[i]) / dt - speed[i])
            val a = alpha(minCutoff + beta * abs(speed[i]), dt)
            previous[i] + a * (value[i] - previous[i])
        }
        x = result
        t = time
        return result.copyOf()
    }
}

/**
 * Numărătoarea live (RepCounter din src/reps.py). Diferența: distanțele se măsoară în secunde, nu în cadre,
 * pentru că telefonul nu dă un număr fix de cadre pe secundă.
 */
class RepCounter(private val prominence: Double, private val minDistanceS: Double = 1.0, private val maxGapS: Double = 2.0) {
    var count = 0
        private set
    private var lastValid: Double? = null
    private var lastPeak: Double? = null
    private var rising = false
    private var valley = Double.POSITIVE_INFINITY
    private var valleyTime = 0.0
    private var top = Double.NEGATIVE_INFINITY
    private var topTime = 0.0

    private fun resetState() {
        rising = false
        valley = Double.POSITIVE_INFINITY
        top = Double.NEGATIVE_INFINITY
    }

    /** Întoarce repetarea (timpii și amplitudinea) când tocmai s-a încheiat una, altfel null. */
    fun update(value: Double, time: Double): RepTimes? {
        if (value.isNaN()) {
            lastValid?.let { if (time - it > maxGapS) resetState() }
            return null
        }
        lastValid = time
        if (!rising) {
            if (value < valley) {
                valley = value
                valleyTime = time
            } else if (value - valley >= prominence) {
                rising = true
                top = value
                topTime = time
            }
            return null
        }
        if (value > top) {
            top = value
            topTime = time
            return null
        }
        if (top - value < prominence) return null

        var rep: RepTimes? = null
        val farEnough = lastPeak.let { it == null || topTime - it >= minDistanceS }
        if (farEnough) {
            count += 1
            lastPeak = topTime
            rep = RepTimes(valleyTime, topTime, time, top - valley)
        }
        rising = false
        valley = value
        valleyTime = time
        top = Double.NEGATIVE_INFINITY
        return rep
    }
}

data class LiveUpdate(
    val status: FrameStatus,
    val angle: Double,
    val reps: Int,
    val newRep: RepTimes?,
    val countdown: Double?, // secundele rămase din numărătoare; null după ea
    val feedback: String?, // un mesaj de spus acum
)

/**
 * Lanțul live pentru un cadru (LiveSession din src/session.py): verificare → netezire → măsuri;
 * în primele countdownS secunde, cadrele bune devin poziția de start; apoi repetări și reguli.
 */
class LiveAnalyzer(
    private val exercise: Exercise,
    private val mirrored: Boolean,
    rulesJson: String,
    private val countdownS: Double = COUNTDOWN_S,
) {
    private val smoother = OneEuroFilter()
    private val counter = RepCounter(exercise.prominence)
    val feedback: FeedbackEngine
    private val startFrames = ArrayList<Map<String, Double>>()
    private var firstT: Double? = null

    init {
        val (settings, rules) = loadRules(rulesJson, exercise.id)
        feedback = FeedbackEngine(rules, settings)
    }

    fun update(image: FloatArray?, world: FloatArray?, time: Double): LiveUpdate {
        val status = judgeFrame(image, world)
        var measures: Map<String, Double>? = null
        if (status == FrameStatus.OK && world != null) {
            val xyz = DoubleArray(33 * 3) { world[(it / 3) * 4 + it % 3].toDouble() }
            val smooth = smoother.filter(xyz, time)
            val smoothWorld = FloatArray(Joints.VALUES) { i -> if (i % 4 == 3) world[i] else smooth[(i / 4) * 3 + i % 4].toFloat() }
            measures = frameMeasures(smoothWorld, mirrored)
        } else {
            smoother.reset() // ca în Python: un cadru respins repornește filtrul
        }

        val remaining = countdownS - (time - (firstT ?: time.also { firstT = it }))
        if (remaining > 0) {
            measures?.let(startFrames::add)
            return LiveUpdate(status, Double.NaN, 0, null, remaining, null)
        }
        if (feedback.baseline == null) feedback.setBaseline(startFrames)

        val angle = measures?.get(primaryMeasure(exercise.id)) ?: Double.NaN
        val rep = counter.update(angle, time)
        val said = feedback.update(time, measures, rep)
        return LiveUpdate(status, angle, counter.count, rep, null, said)
    }

    companion object {
        const val COUNTDOWN_S = 5.0
    }
}
