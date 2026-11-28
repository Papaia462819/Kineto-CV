package ro.kinetocv.app.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import ro.kinetocv.app.ui.formatScore
import ro.kinetocv.app.ui.theme.LocalStatusColors
import kotlin.math.floor

/**
 * Scorurile unui exercițiu în ordinea sesiunilor. Banda verde marchează zona „bine” (peste 40),
 * ca pacientul să vadă dintr-o privire dacă a ajuns acolo, fără să citească cifre.
 */
@Composable
fun ScoreChart(scores: List<Double>, modifier: Modifier = Modifier, height: Dp = 200.dp) {
    val line = MaterialTheme.colorScheme.primary
    val dot = MaterialTheme.colorScheme.surfaceContainerLowest
    val grid = MaterialTheme.colorScheme.outlineVariant
    val zone = LocalStatusColors.current.goodContainer
    val labelStyle = MaterialTheme.typography.labelSmall.copy(color = MaterialTheme.colorScheme.onSurfaceVariant)
    val measurer = rememberTextMeasurer()
    val description = if (scores.isEmpty()) "Grafic gol" else
        "Grafic cu ${scores.size} sesiuni: de la ${formatScore(scores.first())} la ${formatScore(scores.last())} din 50"

    Canvas(modifier.fillMaxWidth().height(height).semantics { contentDescription = description }) {
        if (scores.isEmpty()) return@Canvas
        val lo = (floor((scores.min() - 5) / 10) * 10).coerceIn(0.0, 30.0)
        val hi = 50.0
        val left = 34.dp.toPx()
        val top = 10.dp.toPx()
        val bottom = size.height - 10.dp.toPx()
        val right = size.width - 10.dp.toPx()
        fun y(v: Double) = (top + (1 - (v - lo) / (hi - lo)) * (bottom - top)).toFloat()
        fun x(i: Int) = if (scores.size == 1) (left + right) / 2 else left + i * (right - left) / (scores.size - 1)

        drawRect(zone, Offset(left, y(50.0)), Size(right - left, y(40.0) - y(50.0)))
        var v = lo
        while (v <= hi) {
            drawLine(grid, Offset(left, y(v)), Offset(right, y(v)), 1.dp.toPx())
            val text = measurer.measure("%.0f".format(v), labelStyle)
            drawText(text, topLeft = Offset(0f, y(v) - text.size.height / 2))
            v += 10
        }

        val points = scores.mapIndexed { i, s -> Offset(x(i), y(s)) }
        if (points.size > 1) {
            val path = Path().apply {
                moveTo(points[0].x, points[0].y)
                points.drop(1).forEach { lineTo(it.x, it.y) }
            }
            val area = Path().apply {
                addPath(path)
                lineTo(points.last().x, bottom)
                lineTo(points.first().x, bottom)
                close()
            }
            drawPath(area, Brush.verticalGradient(listOf(line.copy(alpha = 0.22f), line.copy(alpha = 0f)), top, bottom))
            drawPath(path, line, style = Stroke(3.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round))
        }
        points.forEachIndexed { i, p ->
            if (i == points.lastIndex) {
                drawCircle(line, 8.dp.toPx(), p)
                drawCircle(dot, 3.dp.toPx(), p)
            } else {
                drawCircle(dot, 5.dp.toPx(), p)
                drawCircle(line, 5.dp.toPx(), p, style = Stroke(2.5.dp.toPx()))
            }
        }
    }
}
