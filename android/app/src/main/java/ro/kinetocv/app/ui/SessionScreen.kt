package ro.kinetocv.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ro.kinetocv.app.AppContainer
import ro.kinetocv.app.data.Session
import ro.kinetocv.app.pose.Exercises

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SessionScreen(app: AppContainer, id: Int, justRecorded: Boolean, onBack: () -> Unit) {
    val (session, reload) = rememberLoad(id) { app.api.session(id) }
    Scaffold(topBar = {
        TopAppBar(
            title = { Text(if (justRecorded) "Rezultatul tău" else "Sesiune") },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Înapoi") } },
        )
    }) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            when (session) {
                Load.Loading -> LoadingRow()
                is Load.Failed -> ErrorCard(session.message, reload)
                is Load.Ok -> SessionDetails(session.value)
            }
        }
    }
}

@Composable
private fun SessionDetails(s: Session) {
    Text(Exercises.byId(s.exercise).name, style = MaterialTheme.typography.headlineSmall)
    Text(formatDate(s.created), style = MaterialTheme.typography.bodySmall)

    Card(Modifier.fillMaxWidth()) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            ScoreBadge(s.score, size = 72)
            Spacer(Modifier.width(16.dp))
            Column {
                Text("Scor estimat", style = MaterialTheme.typography.titleMedium)
                Text(
                    if (s.score != null) "%.0f din 50 (eroare tipică ±%.0f)".format(s.score, s.scoreError ?: 6.0)
                    else "Nu s-a putut estima",
                )
                Text("Estimare automată, nu un diagnostic.", style = MaterialTheme.typography.bodySmall)
            }
        }
    }

    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Fact("Repetări", "${s.reps ?: 0}")
            Fact("Amplitudine medie", s.romMean?.let { "%.0f°".format(it) } ?: "–")
            Fact("Amplitudinea la final față de început", s.romFatigue?.let { "%.0f%%".format(it * 100) } ?: "–")
            Fact("Durata", s.durationS?.let { "%.0f s".format(it) } ?: "–")
            Fact("Cadre bune", s.kept?.let { "%.0f%%".format(it * 100) } ?: "–")
        }
    }

    if (s.warnings.isNotEmpty()) {
        Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer)) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                s.warnings.forEach { w ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Warning, null)
                        Spacer(Modifier.width(8.dp))
                        Text(w)
                    }
                }
            }
        }
    }

    if (s.feedback.isNotEmpty()) {
        SectionTitle("Observații în timpul exercițiului")
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                s.feedback.forEach { (message, count) ->
                    Row(Modifier.fillMaxWidth()) {
                        Text(message, Modifier.weight(1f))
                        Text(if (count == 1) "o dată" else "de $count ori", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }

    SectionTitle("Recenzia medicului")
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            if (s.reviewText == null) {
                Text("Medicul nu a lăsat încă o recenzie pentru această sesiune.")
            } else {
                Text(s.reviewText)
                Text("${s.reviewAuthor ?: "Medic"} · ${s.reviewCreated?.let(::formatDate) ?: ""}", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun Fact(label: String, value: String) {
    Row(Modifier.fillMaxWidth()) {
        Text(label, Modifier.weight(1f))
        Text(value, style = MaterialTheme.typography.bodyLarge)
    }
}
