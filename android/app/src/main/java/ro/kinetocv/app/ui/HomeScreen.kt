package ro.kinetocv.app.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import ro.kinetocv.app.AppContainer
import ro.kinetocv.app.data.Message
import ro.kinetocv.app.data.Patient
import ro.kinetocv.app.data.Session
import ro.kinetocv.app.pose.Exercises
import java.time.LocalDate
import java.time.LocalDateTime

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(app: AppContainer, open: (Screen) -> Unit) {
    val key = app.settings.serverUrl to app.settings.patientId
    val (patient, reloadPatient) = rememberLoad(key) { app.api.patient() }
    val (sessions, reloadSessions) = rememberLoad(key) { app.api.sessions() }
    val (messages, reloadMessages) = rememberLoad(key) { app.api.messages() }

    Scaffold(topBar = {
        TopAppBar(title = { Text("Kineto-CV") }, actions = {
            IconButton(onClick = { reloadPatient(); reloadSessions(); reloadMessages() }) { Icon(Icons.Default.Refresh, "Reîncarcă") }
            IconButton(onClick = { open(Screen.Settings) }) { Icon(Icons.Default.Settings, "Setări") }
        })
    }) { padding ->
        LazyColumn(
            Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            when (patient) {
                Load.Loading -> item { LoadingRow() }
                is Load.Failed -> item { ErrorCard(patient.message) { reloadPatient(); reloadSessions(); reloadMessages() } }
                is Load.Ok -> {
                    item { PatientCard(patient.value) }
                    item { PlanCard(patient.value, (sessions as? Load.Ok)?.value.orEmpty(), open) }
                }
            }
            if (messages is Load.Ok) item { MessagesCard(messages.value) { open(Screen.Messages) } }
            item { SectionTitle("Sesiuni recente") }
            when (sessions) {
                Load.Loading -> item { LoadingRow() }
                is Load.Failed -> {}
                is Load.Ok -> {
                    if (sessions.value.isEmpty()) item { Text("Nicio sesiune încă.") }
                    items(sessions.value, key = { it.id }) { s -> SessionRow(s) { open(Screen.SessionDetail(s.id)) } }
                }
            }
        }
    }
}

@Composable
private fun PatientCard(patient: Patient) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(patient.name, style = MaterialTheme.typography.headlineSmall)
            patient.birthYear?.let { Text("${LocalDate.now().year - it} ani") }
            patient.diagnosis?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
            patient.therapist?.let { Text("Medic: $it", style = MaterialTheme.typography.bodySmall) }
        }
    }
}

@Composable
private fun PlanCard(patient: Patient, sessions: List<Session>, open: (Screen) -> Unit) {
    val weekAgo = LocalDateTime.now().minusDays(7)
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Planul tău", style = MaterialTheme.typography.titleMedium)
            patient.plan.forEach { item ->
                val exercise = Exercises.byId(item.exercise)
                val done = sessions.count { s ->
                    s.exercise == item.exercise && runCatching { LocalDateTime.parse(s.created).isAfter(weekAgo) }.getOrDefault(false)
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(exercise.name, style = MaterialTheme.typography.bodyLarge)
                        Text("${item.reps} repetări · ${item.perWeek}× pe săptămână · făcut $done/${item.perWeek} în ultimele 7 zile",
                            style = MaterialTheme.typography.bodySmall)
                    }
                    Button(onClick = { open(Screen.Record(item.exercise)) }) {
                        Icon(Icons.Default.PlayArrow, null)
                        Spacer(Modifier.width(4.dp))
                        Text("Start")
                    }
                }
            }
            OutlinedButton(onClick = { open(Screen.Exercises) }) { Text("Alt exercițiu") }
        }
    }
}

@Composable
private fun MessagesCard(messages: List<Message>, onOpen: () -> Unit) {
    val last = messages.lastOrNull { it.authorRole == "doctor" }
    Card(Modifier.fillMaxWidth().clickable(onClick = onOpen)) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.Email, null, tint = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text("Notițe și mesaje de la medic", style = MaterialTheme.typography.titleSmall)
                Text(last?.text ?: "Niciun mesaj încă.", maxLines = 2, overflow = TextOverflow.Ellipsis,
                    style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun SessionRow(session: Session, onClick: () -> Unit) {
    Card(Modifier.fillMaxWidth().clickable(onClick = onClick)) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            ScoreBadge(session.score, size = 44)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(Exercises.byId(session.exercise).name, style = MaterialTheme.typography.bodyLarge)
                Text("${formatDate(session.created)} · ${session.reps ?: 0} repetări", style = MaterialTheme.typography.bodySmall)
            }
            if (session.reviewText != null) {
                Icon(Icons.Default.CheckCircle, "Are recenzie de la medic", tint = MaterialTheme.colorScheme.primary)
            }
        }
    }
}
