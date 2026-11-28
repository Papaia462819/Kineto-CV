package ro.kinetocv.app.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material.icons.automirrored.rounded.TrendingDown
import androidx.compose.material.icons.automirrored.rounded.TrendingFlat
import androidx.compose.material.icons.automirrored.rounded.TrendingUp
import androidx.compose.material.icons.rounded.AccessibilityNew
import androidx.compose.material.icons.rounded.ArrowDownward
import androidx.compose.material.icons.rounded.ArrowUpward
import androidx.compose.material.icons.rounded.Balance
import androidx.compose.material.icons.rounded.Straighten
import androidx.compose.material.icons.rounded.Waves
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import ro.kinetocv.app.data.RepDetail
import ro.kinetocv.app.ui.theme.LocalStatusColors
import java.util.Locale
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.log10
import kotlin.math.pow

/** Ce înseamnă „mai bine” pentru un indice: bara mai mare, mai mică, sau niciuna (ritmul). */
private enum class Better { Higher, Lower, Neither }

/** Propozițiile despre cum s-a schimbat indicele de la primele la ultimele repetări. */
private class Trend(val up: String, val down: String, val same: String, val minAbs: Double, val minRel: Double = 0.0)

/** Un indice al repetărilor: o pagină din carusel. */
private class RepMetric(
    val title: String,
    val icon: ImageVector,
    val explain: String,
    val better: Better,
    val value: (RepDetail) -> Double?,
    val axis: ((Double) -> String)?, // eticheta axei; null = fără cifre (netezimea n-are o unitate pe înțelesul tuturor)
    val describe: (value: Double, mean: Double) -> String, // valoarea unei bare, în cuvinte
    val referenceLabel: String,
    val reference: (List<Double>) -> Double,
    val trend: Trend,
    val baseline: (List<Double>) -> Double = { 0.0 }, // de unde pornesc barele
)

private fun average(values: List<Double>) = values.average()

private val romanian: Locale = Locale.forLanguageTag("ro")

private fun metricsFor(exercise: Int): List<RepMetric> {
    val degrees: (Double) -> String = { String.format(romanian, "%.0f°", it) }
    // Virgulă zecimală, ca în română; pe axă, „2 s” în loc de „2,0 s”.
    val seconds: (Double) -> String = { String.format(romanian, if (it % 1.0 == 0.0) "%.0f s" else "%.1f s", it) }
    val compensated = when (exercise) {
        3 -> "Cât s-a rotit bazinul, care ar trebui să stea pe loc."
        4 -> "Cât s-au rotit umerii, care ar trebui să stea pe loc."
        else -> "Cât s-a aplecat trunchiul în față sau în spate."
    }
    return listOf(
        RepMetric(
            "Amplitudinea", Icons.Rounded.Straighten, "Cât de amplă a fost mișcarea la fiecare repetare. Mai mult e mai bine.",
            Better.Higher, { it.rom }, degrees, { v, _ -> degrees(v) },
            "media primelor 3 repetări", { average(it.take(3)) },
            Trend("Spre final, mișcarea a crescut.", "Spre final, mișcarea a scăzut: poate fi oboseală.",
                "Ai păstrat mișcarea până la final.", minAbs = 3.0, minRel = 0.08),
        ),
        RepMetric(
            "Urcarea", Icons.Rounded.ArrowUpward, "Cât a durat ridicarea. Lent și controlat e mai bine decât repede.",
            Better.Neither, { it.upS }, seconds, { v, _ -> seconds(v) }, "media seriei", ::average,
            Trend("Spre final ai urcat mai încet.", "Spre final ai urcat mai repede.", "Ai urcat în același ritm.",
                minAbs = 0.2, minRel = 0.15),
        ),
        RepMetric(
            "Coborârea", Icons.Rounded.ArrowDownward, "Cât a durat coborârea. Lent și controlat e mai bine decât repede.",
            Better.Neither, { it.downS }, seconds, { v, _ -> seconds(v) }, "media seriei", ::average,
            Trend("Spre final ai coborât mai încet.", "Spre final ai coborât mai repede.", "Ai coborât în același ritm.",
                minAbs = 0.2, minRel = 0.15),
        ),
        RepMetric(
            "Netezimea", Icons.Rounded.Waves, "Cât de lină a fost mișcarea, fără smucituri. Bara mai mică înseamnă mai lin.",
            // Jerk-ul variază de la sute la mii: pe scară logaritmică, o dublare arată la fel oriunde.
            Better.Lower, { d -> d.jerk?.takeIf { it > 0 }?.let(::log10) }, null,
            { v, mean ->
                when {
                    v < mean - 0.1 -> "mai lină decât media seriei"
                    v > mean + 0.1 -> "mai smucită decât media seriei"
                    else -> "cam ca media seriei"
                }
            },
            "media seriei", ::average,
            Trend("Spre final, mișcarea a devenit mai smucită.", "Spre final, mișcarea a devenit mai lină.",
                "Mișcarea a fost la fel de lină.", minAbs = 0.15),
            // Pe scara logaritmică nu există un zero firesc: barele pornesc cu o jumătate de treaptă sub cea mai mică.
            baseline = { values -> floor(values.min() * 2) / 2 - 0.5 },
        ),
        RepMetric(
            "Compensarea", Icons.Rounded.AccessibilityNew, "$compensated Mai puțin e mai bine.",
            Better.Lower, { it.compensation }, degrees, { v, _ -> degrees(v) }, "media seriei", ::average,
            Trend("Spre final ai compensat mai mult: poate fi oboseală.", "Spre final ai compensat mai puțin.",
                "Ai compensat la fel pe toată seria.", minAbs = 2.0, minRel = 0.2),
        ),
        RepMetric(
            "Simetria", Icons.Rounded.Balance, "Diferența dintre partea stângă și cea dreaptă. Mai puțin e mai bine.",
            Better.Lower, { it.asymmetry }, degrees, { v, _ -> degrees(v) }, "media seriei", ::average,
            Trend("Spre final, diferența stânga–dreapta a crescut.", "Spre final, diferența stânga–dreapta a scăzut.",
                "Diferența stânga–dreapta a rămas la fel.", minAbs = 3.0, minRel = 0.2),
        ),
    )
}

/**
 * Evoluția repetărilor dintr-o serie: o pagină pe indice (amplitudinea întâi), cu swipe sau cu săgeți.
 * Bara atinsă rămâne aleasă și când treci la alt indice, ca să vezi aceeași repetare din toate unghiurile.
 */
@Composable
fun RepetitionCharts(details: List<RepDetail>, exercise: Int, modifier: Modifier = Modifier) {
    val pages = remember(details, exercise) { metricsFor(exercise).filter { m -> details.count { m.value(it) != null } >= 2 } }
    if (pages.isEmpty()) return
    val pager = rememberPagerState { pages.size }
    val scope = rememberCoroutineScope()
    var selected by remember(details) { mutableStateOf<Int?>(null) }

    AppCard(modifier) {
        HorizontalPager(pager, pageSpacing = 32.dp, verticalAlignment = Alignment.Top) { page ->
            MetricPage(pages[page], details, selected) { tapped -> selected = if (selected == tapped) null else tapped }
        }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            FilledTonalIconButton(
                onClick = { scope.launch { pager.animateScrollToPage(pager.currentPage - 1) } },
                enabled = pager.currentPage > 0,
                modifier = Modifier.size(52.dp),
            ) { Icon(Icons.AutoMirrored.Rounded.KeyboardArrowLeft, "Indicele anterior", Modifier.size(30.dp)) }
            Row(Modifier.weight(1f), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                pages.forEachIndexed { i, metric ->
                    val current = i == pager.currentPage
                    Box(
                        Modifier.size(32.dp).clickable { scope.launch { pager.animateScrollToPage(i) } }
                            .semantics { contentDescription = "${metric.title}, pagina ${i + 1} din ${pages.size}" },
                        contentAlignment = Alignment.Center,
                    ) {
                        Box(
                            Modifier.size(if (current) 14.dp else 10.dp).background(
                                if (current) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant, CircleShape,
                            ),
                        )
                    }
                }
            }
            FilledTonalIconButton(
                onClick = { scope.launch { pager.animateScrollToPage(pager.currentPage + 1) } },
                enabled = pager.currentPage < pages.lastIndex,
                modifier = Modifier.size(52.dp),
            ) { Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, "Indicele următor", Modifier.size(30.dp)) }
        }
    }
}

@Composable
private fun MetricPage(metric: RepMetric, details: List<RepDetail>, selected: Int?, onSelect: (Int) -> Unit) {
    val values = details.map(metric.value)
    val known = values.filterNotNull()
    val mean = average(known)
    val reference = metric.reference(known)
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconBubble(metric.icon, size = 44.dp)
            Spacer(Modifier.width(12.dp))
            Text(metric.title, style = MaterialTheme.typography.titleLarge)
        }
        Text(metric.explain, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, minLines = 2)
        val value = selected?.let { values.getOrNull(it) }
        Text(
            when {
                selected == null -> "Atinge o bară ca să vezi repetarea."
                value == null -> "Repetarea ${selected + 1}: nemăsurată"
                else -> "Repetarea ${selected + 1}: ${metric.describe(value, mean)}"
            },
            style = MaterialTheme.typography.titleSmall,
            color = if (selected == null) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,
        )
        RepBars(values, reference, metric.baseline(known), selected, onSelect, metric.axis,
            description = "${metric.title} pe repetări: " + values.joinToString { v -> v?.let { metric.axis?.invoke(it) ?: "" } ?: "–" })
        Row(verticalAlignment = Alignment.CenterVertically) {
            val dash = MaterialTheme.colorScheme.onSurfaceVariant
            Canvas(Modifier.width(28.dp).height(12.dp)) {
                drawLine(dash, Offset(0f, size.height / 2), Offset(size.width, size.height / 2), 2.dp.toPx(),
                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(6.dp.toPx(), 4.dp.toPx())))
            }
            Spacer(Modifier.width(8.dp))
            Text("Linia punctată: ${metric.referenceLabel}", style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        TrendLine(metric, known)
    }
}

/** Propoziția de tendință: ultima treime a seriei față de prima. */
@Composable
private fun TrendLine(metric: RepMetric, values: List<Double>) {
    val status = LocalStatusColors.current
    val neutral = MaterialTheme.colorScheme.onSurfaceVariant
    val (icon, color, text) = if (values.size < 3) {
        Triple(Icons.AutoMirrored.Rounded.TrendingFlat, neutral, "Prea puține repetări ca să vedem o tendință.")
    } else {
        val third = maxOf(1, values.size / 3)
        val first = average(values.take(third))
        val change = average(values.takeLast(third)) - first
        val real = abs(change) >= metric.trend.minAbs && abs(change) >= metric.trend.minRel * abs(first)
        when {
            !real -> Triple(Icons.AutoMirrored.Rounded.TrendingFlat, if (metric.better == Better.Neither) neutral else status.good,
                metric.trend.same)
            change > 0 -> Triple(Icons.AutoMirrored.Rounded.TrendingUp,
                when (metric.better) { Better.Higher -> status.good; Better.Lower -> status.medium; Better.Neither -> neutral },
                metric.trend.up)
            else -> Triple(Icons.AutoMirrored.Rounded.TrendingDown,
                when (metric.better) { Better.Higher -> status.medium; Better.Lower -> status.good; Better.Neither -> neutral },
                metric.trend.down)
        }
    }
    Row(verticalAlignment = Alignment.Top) {
        Icon(icon, null, Modifier.size(28.dp), tint = color)
        Spacer(Modifier.width(10.dp))
        Text(text, style = MaterialTheme.typography.bodyLarge, minLines = 2)
    }
}

/** O pas „rotund” pentru axă (1, 2, 2,5 sau 5 × 10ⁿ), ca două trepte să acopere valoarea maximă. */
private fun niceStep(max: Double): Double {
    val raw = (max / 2).coerceAtLeast(1e-6)
    val magnitude = 10.0.pow(floor(log10(raw)))
    return listOf(1.0, 2.0, 2.5, 5.0, 10.0).map { it * magnitude }.first { it >= raw }
}

/** Câte o bară pe repetare, de la zero, cu linia de referință punctată. Atingerea unei bare o alege. */
@Composable
private fun RepBars(
    values: List<Double?>,
    reference: Double,
    baseline: Double,
    selected: Int?,
    onSelect: (Int) -> Unit,
    axis: ((Double) -> String)?,
    description: String,
) {
    val bar = MaterialTheme.colorScheme.primary
    val faded = MaterialTheme.colorScheme.primary.copy(alpha = 0.3f)
    val grid = MaterialTheme.colorScheme.outlineVariant
    val missing = MaterialTheme.colorScheme.outline
    val dash = MaterialTheme.colorScheme.onSurface
    val labelStyle = MaterialTheme.typography.labelSmall.copy(color = MaterialTheme.colorScheme.onSurfaceVariant)
    val selectedStyle = labelStyle.copy(color = MaterialTheme.colorScheme.onSurface, fontWeight = FontWeight.Bold)
    val measurer = rememberTextMeasurer()
    val select by rememberUpdatedState(onSelect)
    val top = values.filterNotNull().maxOrNull()?.let { maxOf(it, reference) } ?: (baseline + 1)
    val range = ((top - baseline) * 1.05).coerceAtLeast(1e-6)
    val step = niceStep(range)
    val yMax = baseline + step * ceil(range / step)

    Canvas(
        Modifier.fillMaxWidth().height(190.dp)
            .semantics { contentDescription = description }
            .pointerInput(values) {
                detectTapGestures { offset ->
                    val left = if (axis != null) 44.dp.toPx() else 4.dp.toPx()
                    val slot = (size.width - left) / values.size
                    val index = ((offset.x - left) / slot).toInt()
                    if (offset.x >= left && index in values.indices) select(index)
                }
            },
    ) {
        val left = if (axis != null) 44.dp.toPx() else 4.dp.toPx()
        val bottom = size.height - 24.dp.toPx()
        val topY = 8.dp.toPx()
        fun y(v: Double) = (bottom - (v - baseline) / (yMax - baseline) * (bottom - topY)).toFloat()

        // Liniile orizontale, cu cifre doar unde unitatea are sens.
        var v = baseline
        while (v <= yMax + 1e-9) {
            drawLine(grid, Offset(left, y(v)), Offset(size.width, y(v)), 1.dp.toPx())
            if (axis != null) {
                val text = measurer.measure(axis(v), labelStyle)
                drawText(text, topLeft = Offset(0f, y(v) - text.size.height / 2))
            }
            v += step
        }

        val slot = (size.width - left) / values.size
        val width = minOf(slot * 0.62f, 36.dp.toPx())
        val labelEvery = if (values.size <= 12) 1 else if (values.size <= 24) 2 else 5
        values.forEachIndexed { i, value ->
            val center = left + slot * (i + 0.5f)
            val chosen = selected == null || selected == i
            if (value == null) {
                drawLine(missing, Offset(center - width / 2, bottom - 2.dp.toPx()), Offset(center + width / 2, bottom - 2.dp.toPx()),
                    3.dp.toPx())
            } else {
                val height = (bottom - y(value)).coerceAtLeast(3.dp.toPx())
                drawRoundRect(if (chosen) bar else faded, Offset(center - width / 2, bottom - height), Size(width, height),
                    CornerRadius(6.dp.toPx()))
            }
            if ((i + 1) % labelEvery == 0 || i == 0 || selected == i) {
                val text = measurer.measure("${i + 1}", if (selected == i) selectedStyle else labelStyle)
                drawText(text, topLeft = Offset(center - text.size.width / 2, bottom + 4.dp.toPx()))
            }
        }
        drawLine(dash, Offset(left, y(reference)), Offset(size.width, y(reference)), 2.dp.toPx(),
            pathEffect = PathEffect.dashPathEffect(floatArrayOf(6.dp.toPx(), 4.dp.toPx())))
    }
}
