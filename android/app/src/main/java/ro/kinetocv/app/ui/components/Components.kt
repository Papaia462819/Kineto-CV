package ro.kinetocv.app.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.RemoveCircle
import androidx.compose.material.icons.rounded.Error
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonColors
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ro.kinetocv.app.ui.Level
import ro.kinetocv.app.ui.dayLetter
import ro.kinetocv.app.ui.dayName
import ro.kinetocv.app.ui.formatScore
import ro.kinetocv.app.ui.levelColors
import ro.kinetocv.app.ui.levelOf
import ro.kinetocv.app.ui.theme.Space
import java.time.LocalDate

/** Cardul de bază: alb pe fundalul gri-verzui, colțuri mari, contur fin (se vede și cu contrast slab). */
@Composable
fun AppCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    color: Color = MaterialTheme.colorScheme.surfaceContainerLowest,
    border: Boolean = true,
    padding: PaddingValues = PaddingValues(Space.inner),
    content: @Composable ColumnScope.() -> Unit,
) {
    val stroke = if (border) BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant) else null
    val inner: @Composable () -> Unit = {
        Column(Modifier.padding(padding), verticalArrangement = Arrangement.spacedBy(12.dp), content = content)
    }
    if (onClick != null) {
        Surface(onClick = onClick, modifier = modifier.fillMaxWidth(), shape = MaterialTheme.shapes.large, color = color,
            border = stroke, content = inner)
    } else {
        Surface(modifier = modifier.fillMaxWidth(), shape = MaterialTheme.shapes.large, color = color, border = stroke, content = inner)
    }
}

/** Titlul mare din capul unui tab. */
@Composable
fun ScreenHeader(title: String, subtitle: String? = null, trailing: @Composable (() -> Unit)? = null) {
    Row(Modifier.fillMaxWidth().padding(top = 8.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            subtitle?.let {
                Text(it, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(title, style = MaterialTheme.typography.headlineMedium, modifier = Modifier.semantics { heading() })
        }
        trailing?.invoke()
    }
}

/** Titlul unei secțiuni, cu o acțiune opțională în dreapta („Vezi tot”). */
@Composable
fun SectionHeader(title: String, action: String? = null, onAction: (() -> Unit)? = null) {
    Row(Modifier.fillMaxWidth().padding(top = 12.dp).heightIn(min = 48.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(title, style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f).semantics { heading() })
        if (action != null && onAction != null) {
            Surface(onClick = onAction, shape = CircleShape, color = Color.Transparent) {
                Text(action, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 12.dp))
            }
        }
    }
}

/** Butonul principal al unei pagini: mare, pe toată lățimea, cu iconiță și text. */
@Composable
fun PrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    icon: ImageVector? = null,
    enabled: Boolean = true,
    colors: ButtonColors = ButtonDefaults.buttonColors(),
) {
    Button(onClick, modifier.fillMaxWidth().heightIn(min = 60.dp), enabled = enabled, colors = colors,
        shape = MaterialTheme.shapes.medium, contentPadding = PaddingValues(horizontal = 24.dp, vertical = 14.dp)) {
        ButtonContent(text, icon)
    }
}

/** Buton secundar, colorat discret. */
@Composable
fun SecondaryButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, icon: ImageVector? = null) {
    FilledTonalButton(onClick, modifier.heightIn(min = 56.dp), shape = MaterialTheme.shapes.medium,
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 12.dp)) {
        ButtonContent(text, icon)
    }
}

@Composable
private fun RowScope.ButtonContent(text: String, icon: ImageVector?) {
    if (icon != null) {
        Icon(icon, null, Modifier.size(26.dp))
        Spacer(Modifier.width(10.dp))
    }
    Text(text, style = MaterialTheme.typography.labelLarge.copy(fontSize = 18.sp))
}

/** O iconiță într-un cerc colorat: semnul vizual al unui card sau al unui rând. */
@Composable
fun IconBubble(
    icon: ImageVector,
    modifier: Modifier = Modifier,
    container: Color = MaterialTheme.colorScheme.primaryContainer,
    tint: Color = MaterialTheme.colorScheme.onPrimaryContainer,
    size: Dp = 48.dp,
) {
    Box(modifier.size(size).background(container, CircleShape), contentAlignment = Alignment.Center) {
        Icon(icon, null, Modifier.size(size * 0.52f), tint = tint)
    }
}

/** Inițialele unei persoane într-un cerc. */
@Composable
fun Avatar(
    initials: String,
    size: Dp = 48.dp,
    container: Color = MaterialTheme.colorScheme.secondaryContainer,
    content: Color = MaterialTheme.colorScheme.onSecondaryContainer,
) {
    Box(Modifier.size(size).background(container, CircleShape), contentAlignment = Alignment.Center) {
        Text(initials, color = content, fontWeight = FontWeight.Bold, fontSize = (size.value * 0.36f).sp)
    }
}

/** Eticheta nivelului: iconiță + cuvânt pe fundal colorat (nu doar culoare). */
@Composable
fun LevelPill(score: Double?, modifier: Modifier = Modifier) {
    val level = levelOf(score)
    val colors = levelColors(level)
    val icon = when (level) {
        Level.Good -> Icons.Rounded.CheckCircle
        Level.Medium -> Icons.Rounded.RemoveCircle
        else -> Icons.Rounded.Error
    }
    Row(
        modifier.background(colors.container, CircleShape).padding(start = 8.dp, end = 12.dp, top = 4.dp, bottom = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, null, Modifier.size(18.dp), tint = colors.main)
        Spacer(Modifier.width(6.dp))
        Text(level.label, style = MaterialTheme.typography.labelMedium, color = colors.onContainer)
    }
}

/** Un inel de progres (0–1), cu orice în mijloc. */
@Composable
fun ProgressRing(
    progress: Float,
    modifier: Modifier = Modifier,
    size: Dp = 96.dp,
    stroke: Dp = 10.dp,
    color: Color = MaterialTheme.colorScheme.primary,
    track: Color = MaterialTheme.colorScheme.surfaceContainerHighest,
    content: @Composable BoxScope.() -> Unit = {},
) {
    Box(modifier.size(size), contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) {
            val w = stroke.toPx()
            val arc = Size(this.size.width - w, this.size.height - w)
            val topLeft = Offset(w / 2, w / 2)
            drawArc(track, 0f, 360f, false, topLeft, arc, style = Stroke(w))
            if (progress > 0f) {
                drawArc(color, -90f, 360f * progress.coerceIn(0f, 1f), false, topLeft, arc, style = Stroke(w, cap = StrokeCap.Round))
            }
        }
        content()
    }
}

/** Scorul (0–50) ca inel colorat după nivel, cu numărul în mijloc. */
@Composable
fun ScoreRing(score: Double?, size: Dp = 72.dp, modifier: Modifier = Modifier) {
    val colors = levelColors(levelOf(score))
    val big = size >= 100.dp
    ProgressRing(
        progress = ((score ?: 0.0) / 50.0).toFloat(),
        size = size,
        stroke = if (big) 14.dp else 7.dp,
        color = colors.main,
        track = colors.container,
        modifier = modifier.semantics(mergeDescendants = true) {
            contentDescription = "Scor ${formatScore(score)} din 50"
        },
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(formatScore(score), fontWeight = FontWeight.Bold, fontSize = (size.value * 0.32f).sp,
                lineHeight = (size.value * 0.34f).sp, color = MaterialTheme.colorScheme.onSurface)
            if (big) Text("din 50", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

/** O cifră importantă cu eticheta ei: „10 / Repetări”. */
@Composable
fun StatTile(icon: ImageVector, value: String, label: String, modifier: Modifier = Modifier) {
    Surface(modifier, shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceContainerLow) {
        Column(Modifier.padding(16.dp).semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Icon(icon, null, Modifier.size(26.dp), tint = MaterialTheme.colorScheme.primary)
            Text(value, style = MaterialTheme.typography.headlineSmall, maxLines = 1)
            Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}

/** Ultimele 7 zile: litera zilei și o bifă unde a fost cel puțin o sesiune. */
@Composable
fun WeekStrip(days: List<Pair<LocalDate, Int>>, modifier: Modifier = Modifier) {
    val today = LocalDate.now()
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        days.forEach { (day, count) ->
            val done = count > 0
            val isToday = day == today
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(6.dp),
                modifier = Modifier.semantics(mergeDescendants = true) {
                    contentDescription = (if (isToday) "Azi" else dayName(day)) + if (done) ", exerciții făcute" else ", fără exerciții"
                },
            ) {
                Text(dayLetter(day), style = MaterialTheme.typography.labelMedium,
                    color = if (isToday) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                    fontWeight = if (isToday) FontWeight.Bold else FontWeight.Medium)
                val ring = if (isToday) Modifier.border(2.dp, MaterialTheme.colorScheme.primary, CircleShape) else Modifier
                Box(
                    Modifier.size(38.dp).then(ring).background(
                        if (done) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceContainerHigh, CircleShape,
                    ),
                    contentAlignment = Alignment.Center,
                ) {
                    if (done) Icon(Icons.Rounded.Check, null, Modifier.size(22.dp), tint = MaterialTheme.colorScheme.onPrimary)
                }
            }
        }
    }
}

/** Câte din cele planificate pe săptămână s-au făcut: buline pline și goale. */
@Composable
fun DotsProgress(done: Int, total: Int, modifier: Modifier = Modifier) {
    Row(
        modifier.semantics(mergeDescendants = true) { contentDescription = "$done din $total săptămâna aceasta" },
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        repeat(total) { i ->
            Box(
                Modifier.size(14.dp).background(
                    if (i < done) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceContainerHighest, CircleShape,
                ),
            )
        }
    }
}

/** Un rând de listă: iconiță, titlu, subtitlu, săgeată. */
@Composable
fun ListRow(
    title: String,
    modifier: Modifier = Modifier,
    subtitle: String? = null,
    leading: @Composable (() -> Unit)? = null,
    trailing: @Composable (() -> Unit)? = { Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, null, tint = MaterialTheme.colorScheme.outline) },
    onClick: (() -> Unit)? = null,
) {
    val body: @Composable () -> Unit = {
        Row(Modifier.defaultMinSize(minHeight = 72.dp).padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically) {
            leading?.let {
                it()
                Spacer(Modifier.width(16.dp))
            }
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleMedium)
                subtitle?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
            trailing?.let {
                Spacer(Modifier.width(8.dp))
                it()
            }
        }
    }
    if (onClick != null) {
        Surface(onClick = onClick, modifier = modifier.fillMaxWidth(), color = Color.Transparent, content = body)
    } else {
        Box(modifier.fillMaxWidth()) { body() }
    }
}

/** Pagina unui detaliu (deasupra taburilor): bară cu „Înapoi”, conținut, buton fix jos opțional. */
@Composable
fun DetailScaffold(
    title: String,
    onBack: () -> Unit,
    bottomBar: @Composable (() -> Unit)? = null,
    content: @Composable (PaddingValues) -> Unit,
) {
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            Row(
                Modifier.fillMaxWidth().windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Top + WindowInsetsSides.Horizontal))
                    .padding(start = 4.dp, end = Space.screen, top = 8.dp, bottom = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack, modifier = Modifier.size(56.dp)) {
                    Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Înapoi", Modifier.size(28.dp))
                }
                Text(title, style = MaterialTheme.typography.titleLarge, maxLines = 1, overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.semantics { heading() })
            }
        },
        bottomBar = {
            if (bottomBar != null) {
                Surface(color = MaterialTheme.colorScheme.background) {
                    Box(Modifier.windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Bottom + WindowInsetsSides.Horizontal))
                        .padding(horizontal = Space.screen, vertical = 12.dp)) { bottomBar() }
                }
            }
        },
        content = content,
    )
}

/** Mesaj pentru o listă goală. */
@Composable
fun EmptyState(icon: ImageVector, title: String, text: String) {
    Column(Modifier.fillMaxWidth().padding(vertical = 32.dp, horizontal = 16.dp), horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(10.dp)) {
        IconBubble(icon, size = 72.dp, container = MaterialTheme.colorScheme.surfaceContainerHigh, tint = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(title, style = MaterialTheme.typography.titleMedium, textAlign = TextAlign.Center)
        Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
    }
}
