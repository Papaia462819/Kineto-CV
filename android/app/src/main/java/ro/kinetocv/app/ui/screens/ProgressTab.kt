package ro.kinetocv.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.TrendingDown
import androidx.compose.material.icons.automirrored.rounded.TrendingFlat
import androidx.compose.material.icons.automirrored.rounded.TrendingUp
import androidx.compose.material.icons.rounded.CalendarMonth
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Forum
import androidx.compose.material.icons.rounded.HourglassEmpty
import androidx.compose.material.icons.rounded.Insights
import androidx.compose.material.icons.rounded.Repeat
import androidx.compose.material.icons.rounded.Speed
import androidx.compose.material.icons.rounded.Straighten
import androidx.compose.material.icons.rounded.Timer
import androidx.compose.material.icons.rounded.TipsAndUpdates
import androidx.compose.material.icons.rounded.Warning
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import ro.kinetocv.app.AppContainer
import ro.kinetocv.app.data.Session
import ro.kinetocv.app.data.day
import ro.kinetocv.app.pose.Exercises
import ro.kinetocv.app.ui.Navigator
import ro.kinetocv.app.ui.Screen
import ro.kinetocv.app.ui.TabColumn
import ro.kinetocv.app.ui.components.AppCard
import ro.kinetocv.app.ui.components.Avatar
import ro.kinetocv.app.ui.components.DetailScaffold
import ro.kinetocv.app.ui.components.EmptyState
import ro.kinetocv.app.ui.components.ExercisePictogram
import ro.kinetocv.app.ui.components.IconBubble
import ro.kinetocv.app.ui.components.LevelPill
import ro.kinetocv.app.ui.components.PrimaryButton
import ro.kinetocv.app.ui.components.RepetitionCharts
import ro.kinetocv.app.ui.components.ScoreChart
import ro.kinetocv.app.ui.components.ScoreRing
import ro.kinetocv.app.ui.components.ScreenHeader
import ro.kinetocv.app.ui.components.SectionHeader
import ro.kinetocv.app.ui.components.StatTile
import ro.kinetocv.app.ui.relativeDay
import ro.kinetocv.app.ui.relativeDayTime
import ro.kinetocv.app.ui.theme.LocalStatusColors
import ro.kinetocv.app.ui.theme.Space
import java.time.LocalDate

/** Progresul: câteva cifre mari, graficul scorului pe exercițiu și istoricul sesiunilor. */
@Composable
fun ProgressTab(app: AppContainer, nav: Navigator, padding: PaddingValues) {
    val repo = app.repo
    val sessions = repo.sessions
    val withSessions = Exercises.all.map { it.id }.filter { id -> sessions.any { it.exercise == id } }
    var selected by rememberSaveable { mutableIntStateOf(withSessions.firstOrNull() ?: 1) }

    TabColumn(padding) {
        item { ScreenHeader("Progresul meu", subtitle = "Ultimele 30 de zile") }
        if (sessions.isEmpty()) {
            item { EmptyState(Icons.Rounded.Insights, "Încă nu ai rezultate", "După primul exercițiu, aici vezi cum progresezi.") }
            return@TabColumn
        }
        item { Stats(sessions) }
        item {
            AppCard {
                Text("Scorul în timp", style = MaterialTheme.typography.titleLarge)
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    withSessions.forEach { id ->
                        FilterChip(
                            selected = id == selected,
                            onClick = { selected = id },
                            label = { Text(Exercises.byId(id).name, style = MaterialTheme.typography.labelLarge) },
                            leadingIcon = if (id == selected) { { Icon(Icons.Rounded.Check, null, Modifier.size(20.dp)) } } else null,
                            modifier = Modifier.heightIn(min = 48.dp),
                            shape = CircleShape,
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = MaterialTheme.colorScheme.primaryContainer,
                                selectedLabelColor = MaterialTheme.colorScheme.onPrimaryContainer,
                                selectedLeadingIconColor = MaterialTheme.colorScheme.onPrimaryContainer,
                            ),
                        )
                    }
                }
                val scores = sessions.filter { it.exercise == selected }.sortedBy { it.created }.mapNotNull { it.score }
                Trend(scores)
                ScoreChart(scores)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Spacer(Modifier.size(18.dp).background(LocalStatusColors.current.goodContainer, MaterialTheme.shapes.extraSmall))
                    Spacer(Modifier.width(8.dp))
                    Text("Zona verde: rezultat bun (peste 40 din 50)", style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        item { SectionHeader("Istoric") }
        sessions.forEach { s -> item(key = s.id) { SessionRow(s) { nav.open(Screen.SessionDetail(s.id)) } } }
    }
}

@Composable
private fun Stats(sessions: List<Session>) {
    val from = LocalDate.now().minusDays(29)
    val month = sessions.filter { s -> s.day()?.let { !it.isBefore(from) } == true }
    val average = month.mapNotNull { it.score }.average().takeIf { !it.isNaN() }
    val minutes = month.sumOf { it.durationS ?: 0.0 } / 60
    Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        StatTile(Icons.Rounded.CalendarMonth, "${month.size}", "sesiuni", Modifier.weight(1f).fillMaxHeight())
        StatTile(Icons.Rounded.Insights, average?.let { "%.0f".format(it) } ?: "–", "scor mediu", Modifier.weight(1f).fillMaxHeight())
        StatTile(Icons.Rounded.Timer, "%.0f".format(minutes), "minute", Modifier.weight(1f).fillMaxHeight())
    }
}

/** O propoziție despre tendință: „+12 puncte față de prima sesiune”. */
@Composable
private fun Trend(scores: List<Double>) {
    if (scores.size < 2) return
    val change = scores.last() - scores.first()
    val status = LocalStatusColors.current
    val (icon, color, text) = when {
        change >= 3 -> Triple(Icons.AutoMirrored.Rounded.TrendingUp, status.good, "Ai progresat cu %.0f puncte".format(change))
        change <= -3 -> Triple(Icons.AutoMirrored.Rounded.TrendingDown, status.weak, "Scor mai mic cu %.0f puncte".format(-change))
        else -> Triple(Icons.AutoMirrored.Rounded.TrendingFlat, MaterialTheme.colorScheme.onSurfaceVariant, "Rezultate constante")
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, Modifier.size(28.dp), tint = color)
        Spacer(Modifier.width(8.dp))
        Text(text, style = MaterialTheme.typography.titleSmall)
    }
}

@Composable
private fun SessionRow(session: Session, onClick: () -> Unit) {
    AppCard(onClick = onClick, padding = PaddingValues(16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            ScoreRing(session.score, size = 60.dp)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(Exercises.byId(session.exercise).name, style = MaterialTheme.typography.titleMedium)
                Text("${relativeDay(session.created)} · ${session.reps ?: 0} repetări", style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (session.reviewText != null) {
                Icon(Icons.Rounded.Forum, "Medicul a lăsat o părere", Modifier.size(26.dp), tint = MaterialTheme.colorScheme.primary)
            }
        }
    }
}

/** Rezultatul unei sesiuni: scorul mare, câteva cifre, ce se poate îmbunătăți și părerea medicului. */
@Composable
fun SessionDetailScreen(app: AppContainer, id: Int, justRecorded: Boolean, nav: Navigator) {
    val session = app.repo.session(id)
    DetailScaffold(
        title = if (justRecorded) "Rezultatul tău" else "Detalii sesiune",
        onBack = nav.back,
        bottomBar = if (justRecorded) { { PrimaryButton("Gata", onClick = nav.back, icon = Icons.Rounded.Check) } } else null,
    ) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(horizontal = Space.screen, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(Space.gap),
        ) {
            if (session == null) {
                EmptyState(Icons.Rounded.HourglassEmpty, "Sesiunea nu mai există", "Întoarce-te și alege alta din istoric.")
            } else {
                SessionDetails(session, justRecorded, app)
            }
        }
    }
}

@Composable
private fun SessionDetails(s: Session, justRecorded: Boolean, app: AppContainer) {
    val exercise = Exercises.byId(s.exercise)
    AppCard {
        Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (justRecorded) {
                Text("Bravo, ai terminat!", style = MaterialTheme.typography.headlineSmall, textAlign = TextAlign.Center)
            }
            ScoreRing(s.score, size = 148.dp)
            LevelPill(s.score)
            Row(verticalAlignment = Alignment.CenterVertically) {
                ExercisePictogram(s.exercise, size = 44.dp)
                Spacer(Modifier.width(10.dp))
                Column {
                    Text(exercise.name, style = MaterialTheme.typography.titleMedium)
                    Text(relativeDayTime(s.created), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Text(
                "Scor estimat automat (±%.0f puncte). Nu este un diagnostic.".format(s.scoreError ?: 6.0),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
        }
    }

    Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        StatTile(Icons.Rounded.Repeat, "${s.reps ?: 0}", "repetări", Modifier.weight(1f).fillMaxHeight())
        StatTile(Icons.Rounded.Timer, s.durationS?.let { duration(it) } ?: "–", "durată", Modifier.weight(1f).fillMaxHeight())
    }
    Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        StatTile(Icons.Rounded.Straighten, s.romMean?.let { "%.0f°".format(it) } ?: "–", "cât de amplă a fost mișcarea",
            Modifier.weight(1f).fillMaxHeight())
        StatTile(Icons.Rounded.Speed, s.romFatigue?.let { "%.0f%%".format(minOf(it, 1.0) * 100) } ?: "–", "cât ai păstrat mișcarea până la final",
            Modifier.weight(1f).fillMaxHeight())
    }

    if (s.repDetails.size >= 2) {
        SectionHeader("Fiecare repetare")
        RepetitionCharts(s.repDetails, s.exercise)
    }

    if (s.warnings.isNotEmpty()) {
        AppCard(color = MaterialTheme.colorScheme.tertiaryContainer, border = false) {
            s.warnings.forEach { w ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Rounded.Warning, null, tint = MaterialTheme.colorScheme.onTertiaryContainer)
                    Spacer(Modifier.width(10.dp))
                    Text(w, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onTertiaryContainer)
                }
            }
        }
    }

    if (s.feedback.isNotEmpty()) {
        SectionHeader("Ce poți îmbunătăți")
        AppCard {
            s.feedback.entries.sortedByDescending { it.value }.forEach { (message, count) ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconBubble(Icons.Rounded.TipsAndUpdates, size = 40.dp, container = MaterialTheme.colorScheme.tertiaryContainer,
                        tint = MaterialTheme.colorScheme.onTertiaryContainer)
                    Spacer(Modifier.width(12.dp))
                    Text(message, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
                    Spacer(Modifier.width(8.dp))
                    Text(if (count == 1) "o dată" else "de $count ori", style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }

    SectionHeader("Părerea medicului")
    AppCard {
        if (s.reviewText == null) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconBubble(Icons.Rounded.HourglassEmpty, container = MaterialTheme.colorScheme.surfaceContainerHigh,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.width(14.dp))
                Text("Medicul nu a văzut încă această sesiune.", style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
            }
        } else {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Avatar(app.repo.doctor.initials)
                Spacer(Modifier.width(12.dp))
                Column {
                    Text(s.reviewAuthor ?: "Medicul tău", style = MaterialTheme.typography.titleMedium)
                    s.reviewCreated?.let {
                        Text(relativeDayTime(it), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            Text(s.reviewText, style = MaterialTheme.typography.bodyLarge)
        }
    }
}

private fun duration(seconds: Double): String {
    val total = seconds.toInt()
    return if (total < 60) "$total s" else "${total / 60} min ${total % 60} s"
}
