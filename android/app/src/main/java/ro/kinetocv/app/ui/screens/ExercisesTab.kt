package ro.kinetocv.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Accessibility
import androidx.compose.material.icons.rounded.CalendarMonth
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Handyman
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.RecordVoiceOver
import androidx.compose.material.icons.rounded.Repeat
import androidx.compose.material.icons.rounded.Smartphone
import androidx.compose.material.icons.rounded.Timer
import androidx.compose.material.icons.rounded.WarningAmber
import androidx.compose.material.icons.rounded.WbSunny
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ro.kinetocv.app.AppContainer
import ro.kinetocv.app.data.ExerciseGuide
import ro.kinetocv.app.data.MockRepository
import ro.kinetocv.app.data.PlanItem
import ro.kinetocv.app.pose.Exercises
import ro.kinetocv.app.ui.Navigator
import ro.kinetocv.app.ui.Screen
import ro.kinetocv.app.ui.TabColumn
import ro.kinetocv.app.ui.components.AppCard
import ro.kinetocv.app.ui.components.DetailScaffold
import ro.kinetocv.app.ui.components.DotsProgress
import ro.kinetocv.app.ui.components.ExercisePictogram
import ro.kinetocv.app.ui.components.IconBubble
import ro.kinetocv.app.ui.components.PrimaryButton
import ro.kinetocv.app.ui.components.ScreenHeader
import ro.kinetocv.app.ui.components.SectionHeader
import ro.kinetocv.app.ui.theme.Space

/** Exercițiile: întâi cele din planul medicului, apoi restul. */
@Composable
fun ExercisesTab(app: AppContainer, nav: Navigator, padding: PaddingValues) {
    val repo = app.repo
    val planned = repo.patient.plan.map { it.exercise }.toSet()
    TabColumn(padding) {
        item { ScreenHeader("Exercițiile mele", subtitle = "Planul de la ${repo.doctor.name}") }
        repo.patient.plan.forEach { p -> item(key = "plan${p.exercise}") { PlanExerciseCard(p, repo, nav) } }
        item { SectionHeader("Alte exerciții") }
        Exercises.all.filter { it.id !in planned }.forEach { e ->
            item(key = "other${e.id}") {
                AppCard(onClick = { nav.open(Screen.ExerciseDetail(e.id)) }) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        ExercisePictogram(e.id, size = 64.dp, container = MaterialTheme.colorScheme.surfaceContainerHigh,
                            figure = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.width(16.dp))
                        Column(Modifier.weight(1f)) {
                            Text(e.name, style = MaterialTheme.typography.titleMedium)
                            Text("Nu face parte din planul tău", style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun PlanExerciseCard(item: PlanItem, repo: MockRepository, nav: Navigator) {
    val exercise = Exercises.byId(item.exercise)
    val done = repo.doneLastWeek(item.exercise)
    AppCard(onClick = { nav.open(Screen.ExerciseDetail(item.exercise)) }) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            ExercisePictogram(item.exercise, size = 84.dp)
            Spacer(Modifier.width(16.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(exercise.name, style = MaterialTheme.typography.titleLarge)
                Text("${item.reps} repetări · de ${item.perWeek} ori pe săptămână", style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            DotsProgress(minOf(done, item.perWeek), item.perWeek)
            Spacer(Modifier.width(10.dp))
            Text("$done din ${item.perWeek} săptămâna aceasta", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
            if (repo.doneToday(item.exercise)) DonePill("Azi")
        }
        PrimaryButton("Începe", onClick = { nav.open(Screen.Record(item.exercise)) }, icon = Icons.Rounded.PlayArrow)
    }
}

@Composable
private fun DonePill(text: String) {
    Row(
        Modifier.background(MaterialTheme.colorScheme.primaryContainer, CircleShape).padding(start = 8.dp, end = 12.dp, top = 4.dp, bottom = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Rounded.Check, null, Modifier.size(18.dp), tint = MaterialTheme.colorScheme.onPrimaryContainer)
        Spacer(Modifier.width(4.dp))
        Text(text, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onPrimaryContainer)
    }
}

/** Detaliile unui exercițiu: desenul, pașii, pregătirea și butonul de start mereu vizibil jos. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ExerciseDetailScreen(app: AppContainer, exerciseId: Int, nav: Navigator) {
    val exercise = Exercises.byId(exerciseId)
    val plan = app.repo.patient.plan.firstOrNull { it.exercise == exerciseId }
    DetailScaffold(
        title = exercise.name,
        onBack = nav.back,
        bottomBar = { PrimaryButton("Începe exercițiul", onClick = { nav.open(Screen.Record(exerciseId)) }, icon = Icons.Rounded.PlayArrow) },
    ) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(horizontal = Space.screen, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(Space.gap),
        ) {
            ExercisePictogram(exerciseId, Modifier.fillMaxWidth().height(220.dp), size = null)
            Text(exercise.description, style = MaterialTheme.typography.bodyLarge)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (plan != null) {
                    InfoChip(Icons.Rounded.Repeat, "${plan.reps} repetări")
                    InfoChip(Icons.Rounded.CalendarMonth, "${plan.perWeek}× pe săptămână")
                }
                InfoChip(Icons.Rounded.Timer, "~${ExerciseGuide.MINUTES} minute")
            }
            ExerciseGuide.equipment(exerciseId)?.let { thing ->
                AppCard(color = MaterialTheme.colorScheme.secondaryContainer, border = false) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        IconBubble(Icons.Rounded.Handyman, container = MaterialTheme.colorScheme.surfaceContainerLowest,
                            tint = MaterialTheme.colorScheme.secondary)
                        Spacer(Modifier.width(14.dp))
                        Text("Ai nevoie de $thing.", style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSecondaryContainer)
                    }
                }
            }

            SectionHeader("Cum se face")
            AppCard {
                ExerciseGuide.steps(exerciseId).forEachIndexed { i, step ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(40.dp).background(MaterialTheme.colorScheme.primary, CircleShape), contentAlignment = Alignment.Center) {
                            Text("${i + 1}", color = MaterialTheme.colorScheme.onPrimary, fontWeight = FontWeight.Bold,
                                style = MaterialTheme.typography.titleMedium)
                        }
                        Spacer(Modifier.width(14.dp))
                        Text(step, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
                    }
                }
            }

            SectionHeader("Înainte să începi")
            PreparationCard()
            SafetyNote()
        }
    }
}

@Composable
private fun InfoChip(icon: ImageVector, text: String) {
    Row(
        Modifier.background(MaterialTheme.colorScheme.surfaceContainerHigh, CircleShape).padding(horizontal = 14.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, null, Modifier.size(22.dp), tint = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.width(8.dp))
        Text(text, style = MaterialTheme.typography.labelLarge)
    }
}

/** Cum se așază telefonul și pacientul: folosit și în detaliile exercițiului, și în Ajutor. */
@Composable
fun PreparationCard() {
    AppCard {
        PrepRow(Icons.Rounded.Smartphone, "Sprijină telefonul la 2–3 metri, la înălțimea pieptului.")
        PrepRow(Icons.Rounded.Accessibility, "Trebuie să se vadă tot corpul, de la cap la picioare.")
        PrepRow(Icons.Rounded.WbSunny, "Lumina să vină din față, nu din spatele tău.")
        PrepRow(Icons.Rounded.RecordVoiceOver, "Aplicația îți spune cu voce ce să corectezi.")
    }
}

@Composable
private fun PrepRow(icon: ImageVector, text: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        IconBubble(icon)
        Spacer(Modifier.width(14.dp))
        Text(text, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
    }
}

@Composable
fun SafetyNote() {
    AppCard(color = MaterialTheme.colorScheme.tertiaryContainer, border = false) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Rounded.WarningAmber, null, Modifier.size(30.dp), tint = MaterialTheme.colorScheme.onTertiaryContainer)
            Spacer(Modifier.width(12.dp))
            Text("Dacă simți durere ascuțită, oprește-te și scrie-i medicului.", style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onTertiaryContainer)
        }
    }
}
