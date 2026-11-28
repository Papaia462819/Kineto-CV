package ro.kinetocv.app.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin

/**
 * Silueta unui exercițiu, desenată din linii, cu o săgeată pentru mișcare.
 * Același desen apare în listă, în detalii și pe pagina de rezultat, ca pacientul să recunoască exercițiul fără să citească.
 * Exercițiul 0 e o persoană în picioare (poziția de start).
 */
@Composable
fun ExercisePictogram(
    exercise: Int,
    modifier: Modifier = Modifier,
    size: Dp? = 72.dp,
    container: Color = MaterialTheme.colorScheme.primaryContainer,
    figure: Color = MaterialTheme.colorScheme.onPrimaryContainer,
    accent: Color = MaterialTheme.colorScheme.tertiary,
    prop: Color = MaterialTheme.colorScheme.secondary,
) {
    val box = if (size != null) modifier.size(size) else modifier
    Box(box.background(container, MaterialTheme.shapes.medium)) {
        Canvas(Modifier.fillMaxSize().padding(8.dp)) { drawExercise(exercise, figure, accent, prop) }
    }
}

private data class P(val x: Float, val y: Float)

/** Punctele siluetei, într-un pătrat de 100 × 100. */
private data class Pose(
    val head: P, val neck: P, val ls: P, val rs: P, val le: P, val re: P, val lh: P, val rh: P,
    val hip: P, val lhip: P, val rhip: P, val lk: P, val rk: P, val lf: P, val rf: P,
)

private val STANDING = Pose(
    head = P(50f, 20f), neck = P(50f, 31f), ls = P(40f, 33f), rs = P(60f, 33f),
    le = P(36f, 46f), re = P(64f, 46f), lh = P(35f, 59f), rh = P(65f, 59f),
    hip = P(50f, 59f), lhip = P(44f, 59f), rhip = P(56f, 59f),
    lk = P(43f, 77f), rk = P(57f, 77f), lf = P(42f, 94f), rf = P(58f, 94f),
)

private fun P.rotate(c: P, degrees: Float): P {
    val a = Math.toRadians(degrees.toDouble())
    val dx = x - c.x
    val dy = y - c.y
    return P((c.x + dx * cos(a) - dy * sin(a)).toFloat(), (c.y + dx * sin(a) + dy * cos(a)).toFloat())
}

/** Puncte pe o elipsă (sau cerc), între două unghiuri în grade (0 = dreapta, 90 = jos). */
private fun arc(c: P, rx: Float, ry: Float, from: Float, to: Float, steps: Int = 24): List<P> = (0..steps).map {
    val a = Math.toRadians((from + (to - from) * it / steps).toDouble())
    P((c.x + rx * cos(a)).toFloat(), (c.y + ry * sin(a)).toFloat())
}

private fun DrawScope.drawExercise(exercise: Int, figure: Color, accent: Color, prop: Color) {
    val u = size.minDimension / 100f
    val ox = (size.width - 100f * u) / 2
    val oy = (size.height - 100f * u) / 2
    fun o(p: P) = Offset(ox + p.x * u, oy + p.y * u)

    fun person(pose: Pose) {
        val w = 6f * u
        fun bone(a: P, b: P) = drawLine(figure, o(a), o(b), w, StrokeCap.Round)
        bone(pose.neck, pose.hip)
        bone(pose.ls, pose.rs)
        bone(pose.ls, pose.le); bone(pose.le, pose.lh)
        bone(pose.rs, pose.re); bone(pose.re, pose.rh)
        bone(pose.lhip, pose.rhip)
        bone(pose.lhip, pose.lk); bone(pose.lk, pose.lf)
        bone(pose.rhip, pose.rk); bone(pose.rk, pose.rf)
        drawCircle(figure, 7.5f * u, o(pose.head))
    }

    fun stick(y: Float) = drawLine(prop, o(P(18f, y)), o(P(82f, y)), 4f * u, StrokeCap.Round)

    fun head(from: P, tip: P) {
        val angle = atan2(tip.y - from.y, tip.x - from.x)
        listOf(-0.5f, 0.5f).forEach { s ->
            val a = angle + Math.PI.toFloat() + s
            drawLine(accent, o(tip), o(P(tip.x + 7f * cos(a), tip.y + 7f * sin(a))), 3.5f * u, StrokeCap.Round)
        }
    }

    fun arrow(points: List<P>, bothEnds: Boolean = false) {
        val path = Path().apply {
            moveTo(o(points.first()).x, o(points.first()).y)
            points.drop(1).forEach { lineTo(o(it).x, o(it).y) }
        }
        drawPath(path, accent, style = Stroke(3.5f * u, cap = StrokeCap.Round, join = StrokeJoin.Round))
        head(points[points.size - 2], points.last())
        if (bothEnds) head(points[1], points.first())
    }

    when (exercise) {
        1 -> { // brațele urcă prin față deasupra capului
            person(STANDING.copy(le = P(37f, 20f), lh = P(36f, 7f), re = P(63f, 20f), rh = P(64f, 7f)))
            arrow(arc(STANDING.rs, 27f, 27f, 75f, -60f))
            arrow(arc(STANDING.ls, 27f, 27f, 105f, 240f))
        }
        2 -> { // înclinare laterală cu brațele sus
            val c = STANDING.hip
            val up = STANDING.copy(le = P(38f, 19f), lh = P(39f, 6f), re = P(62f, 19f), rh = P(61f, 6f))
            fun r(p: P) = p.rotate(c, -20f)
            person(up.copy(head = r(up.head), neck = r(up.neck), ls = r(up.ls), rs = r(up.rs),
                le = r(up.le), re = r(up.re), lh = r(up.lh), rh = r(up.rh)))
            arrow(arc(c, 58f, 58f, -72f, -108f))
        }
        3 -> { // rotația trunchiului, cu bastonul în față
            person(STANDING.copy(le = P(36f, 41f), lh = P(42f, 35f), re = P(64f, 41f), rh = P(58f, 35f)))
            stick(35f)
            arrow(arc(P(50f, 46f), 34f, 9f, 160f, 20f))
        }
        4 -> { // rotația bazinului, mâinile pe șolduri
            person(STANDING.copy(le = P(31f, 46f), lh = P(43f, 57f), re = P(69f, 46f), rh = P(57f, 57f)))
            arrow(arc(P(50f, 63f), 29f, 8f, 160f, 20f))
        }
        5 -> { // genuflexiune cu bastonul în față
            person(Pose(
                head = P(50f, 32f), neck = P(50f, 43f), ls = P(40f, 45f), rs = P(60f, 45f),
                le = P(36f, 55f), re = P(64f, 55f), lh = P(42f, 50f), rh = P(58f, 50f),
                hip = P(50f, 68f), lhip = P(44f, 68f), rhip = P(56f, 68f),
                lk = P(33f, 79f), rk = P(67f, 79f), lf = P(40f, 94f), rf = P(60f, 94f),
            ))
            stick(50f)
            arrow(listOf(P(88f, 28f), P(88f, 47f), P(88f, 66f)), bothEnds = true)
        }
        else -> person(STANDING)
    }
}
