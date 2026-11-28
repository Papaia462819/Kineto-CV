package ro.kinetocv.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.ui.draw.clip
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Reply
import androidx.compose.material.icons.rounded.EmojiEvents
import androidx.compose.material.icons.rounded.Lightbulb
import androidx.compose.material.icons.rounded.LocalFireDepartment
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.Videocam
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import ro.kinetocv.app.AppContainer
import ro.kinetocv.app.data.ExerciseGuide
import ro.kinetocv.app.data.MockRepository
import ro.kinetocv.app.data.Session
import ro.kinetocv.app.pose.Exercises
import ro.kinetocv.app.ui.Navigator
import ro.kinetocv.app.ui.Screen
import ro.kinetocv.app.ui.Tab
import ro.kinetocv.app.ui.TabColumn
import ro.kinetocv.app.ui.appointmentDate
import ro.kinetocv.app.ui.components.AppCard
import ro.kinetocv.app.ui.components.Avatar
import ro.kinetocv.app.ui.components.ExercisePictogram
import ro.kinetocv.app.ui.components.IconBubble
import ro.kinetocv.app.ui.components.LevelPill
import ro.kinetocv.app.ui.components.PrimaryButton
import ro.kinetocv.app.ui.components.ProgressRing
import ro.kinetocv.app.ui.components.ScoreRing
import ro.kinetocv.app.ui.components.ScreenHeader
import ro.kinetocv.app.ui.components.SecondaryButton
import ro.kinetocv.app.ui.components.WeekStrip
import ro.kinetocv.app.ui.longDate
import ro.kinetocv.app.ui.relativeDay
import ro.kinetocv.app.ui.relativeDayTime
import ro.kinetocv.app.ui.timeOfDayGreeting
import java.time.LocalDate

/** Acasă: ce am de făcut azi, cum stau săptămâna asta și ce mi-a scris medicul. */
@Composable
fun HomeTab(app: AppContainer, nav: Navigator, padding: PaddingValues) {
    val repo = app.repo
    TabColumn(padding) {
        item {
            ScreenHeader("${timeOfDayGreeting()}, ${repo.firstName}", subtitle = longDate(LocalDate.now())) {
                Avatar(repo.initials, size = 52.dp,
                    container = MaterialTheme.colorScheme.primaryContainer, content = MaterialTheme.colorScheme.onPrimaryContainer)
            }
        }
        item { TodayCard(repo, nav) }
        item { WeekCard(repo) }
        item { DoctorNoteCard(repo, nav) }
        item { AppointmentCard(repo) }
        repo.sessions.firstOrNull()?.let { last -> item { LastResultCard(last, nav) } }
        item { TipCard(repo.tipOfTheDay()) }
    }
}

@Composable
private fun TodayCard(repo: MockRepository, nav: Navigator) {
    val next = repo.nextExercise()
    AppCard(color = MaterialTheme.colorScheme.primaryContainer, border = false) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            ProgressRing(
                progress = repo.weeklyDone.toFloat() / repo.weeklyTarget,
                size = 88.dp,
                track = MaterialTheme.colorScheme.surfaceContainerLowest.copy(alpha = 0.7f),
                modifier = Modifier.semantics(mergeDescendants = true) {
                    contentDescription = "${repo.weeklyDone} din ${repo.weeklyTarget} sesiuni săptămâna aceasta"
                },
            ) {
                Text("${repo.weeklyDone}/${repo.weeklyTarget}", style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onPrimaryContainer)
            }
            Spacer(Modifier.width(16.dp))
            Column(Modifier.weight(1f)) {
                Text("Săptămâna aceasta", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onPrimaryContainer)
                Text(
                    "Ai făcut ${repo.weeklyDone} din ${repo.weeklyTarget} sesiuni",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                )
            }
        }
        if (next != null) {
            val exercise = Exercises.byId(next.exercise)
            Row(
                Modifier.clip(MaterialTheme.shapes.medium).background(MaterialTheme.colorScheme.surfaceContainerLowest)
                    .clickable { nav.open(Screen.ExerciseDetail(next.exercise)) }
                    .padding(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                ExercisePictogram(next.exercise, size = 68.dp)
                Spacer(Modifier.width(14.dp))
                Column(Modifier.weight(1f)) {
                    Text("Urmează", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                    Text(exercise.name, style = MaterialTheme.typography.titleLarge, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    Text("${next.reps} repetări · ~${ExerciseGuide.MINUTES} min", style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            PrimaryButton("Începe exercițiul", onClick = { nav.open(Screen.Record(next.exercise)) }, icon = Icons.Rounded.PlayArrow)
        } else {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconBubble(Icons.Rounded.EmojiEvents, container = MaterialTheme.colorScheme.surfaceContainerLowest,
                    tint = MaterialTheme.colorScheme.tertiary, size = 56.dp)
                Spacer(Modifier.width(14.dp))
                Text("Bravo! Ai terminat exercițiile pentru azi.", style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onPrimaryContainer, modifier = Modifier.weight(1f))
            }
            SecondaryButton("Vezi toate exercițiile", onClick = { nav.goTo(Tab.Exercises) })
        }
    }
}

@Composable
private fun WeekCard(repo: MockRepository) {
    val streak = repo.streak()
    AppCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Ultimele 7 zile", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
            if (streak > 0) {
                Row(
                    Modifier.background(MaterialTheme.colorScheme.tertiaryContainer, CircleShape)
                        .padding(start = 8.dp, end = 12.dp, top = 4.dp, bottom = 4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Rounded.LocalFireDepartment, null, Modifier.size(20.dp), tint = MaterialTheme.colorScheme.tertiary)
                    Spacer(Modifier.width(4.dp))
                    Text(if (streak == 1) "1 zi la rând" else "$streak zile la rând", style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onTertiaryContainer)
                }
            }
        }
        WeekStrip(repo.lastSevenDays())
    }
}

@Composable
private fun DoctorNoteCard(repo: MockRepository, nav: Navigator) {
    val last = repo.messages.lastOrNull { it.authorRole == "doctor" } ?: return
    AppCard(onClick = { nav.goTo(Tab.Doctor) }) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Avatar(repo.doctor.initials)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(repo.doctor.name, style = MaterialTheme.typography.titleMedium)
                Text(relativeDayTime(last.created), style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (repo.unread > 0) {
                Text("Nou", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onPrimary,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.background(MaterialTheme.colorScheme.primary, CircleShape).padding(horizontal = 12.dp, vertical = 4.dp))
            }
        }
        Text(last.text, style = MaterialTheme.typography.bodyLarge, maxLines = 3, overflow = TextOverflow.Ellipsis)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.AutoMirrored.Rounded.Reply, null, tint = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.width(8.dp))
            Text("Răspunde medicului", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
        }
    }
}

@Composable
private fun AppointmentCard(repo: MockRepository) {
    val appointment = repo.appointment
    AppCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconBubble(Icons.Rounded.Videocam, container = MaterialTheme.colorScheme.tertiaryContainer,
                tint = MaterialTheme.colorScheme.onTertiaryContainer, size = 56.dp)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text("Următoarea consultație", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(appointmentDate(appointment.time), style = MaterialTheme.typography.titleMedium)
                Text(appointment.title, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun LastResultCard(session: Session, nav: Navigator) {
    AppCard(onClick = { nav.open(Screen.SessionDetail(session.id)) }) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            ScoreRing(session.score, size = 64.dp)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text("Ultimul rezultat · ${relativeDay(session.created)}", style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(Exercises.byId(session.exercise).name, style = MaterialTheme.typography.titleMedium)
                LevelPill(session.score)
            }
        }
    }
}

@Composable
private fun TipCard(tip: String) {
    AppCard(color = MaterialTheme.colorScheme.secondaryContainer, border = false) {
        Row {
            Icon(Icons.Rounded.Lightbulb, null, Modifier.size(28.dp), tint = MaterialTheme.colorScheme.onSecondaryContainer)
            Spacer(Modifier.width(12.dp))
            Column {
                Text("Sfatul zilei", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSecondaryContainer)
                Text(tip, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSecondaryContainer)
            }
        }
    }
}
