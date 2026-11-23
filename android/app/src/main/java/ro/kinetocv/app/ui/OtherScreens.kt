package ro.kinetocv.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import ro.kinetocv.app.AppContainer
import ro.kinetocv.app.data.Message
import ro.kinetocv.app.data.userMessage
import ro.kinetocv.app.pose.Exercises

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun BackScaffold(title: String, onBack: () -> Unit, content: @Composable (PaddingValues) -> Unit) {
    Scaffold(topBar = {
        TopAppBar(
            title = { Text(title) },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Înapoi") } },
        )
    }, content = content)
}

/** Notițele medicului și mesajele pacientului. Mai târziu, aplicația medicului va scrie în același fir. */
@Composable
fun MessagesScreen(app: AppContainer, onBack: () -> Unit) {
    val (loaded, reload) = rememberLoad(app.settings.patientId) { app.api.messages() }
    val (patient, _) = rememberLoad(app.settings.patientId) { app.api.patient() }
    var sent by remember { mutableStateOf<List<Message>?>(null) }
    var draft by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    BackScaffold("Mesaje cu medicul", onBack) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).imePadding()) {
            Box(Modifier.weight(1f)) {
                when (loaded) {
                    Load.Loading -> LoadingRow()
                    is Load.Failed -> Box(Modifier.padding(16.dp)) { ErrorCard(loaded.message, reload) }
                    is Load.Ok -> {
                        val messages = sent ?: loaded.value
                        LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            items(messages, key = { it.id }) { MessageBubble(it) }
                        }
                    }
                }
            }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(horizontal = 16.dp)) }
            Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(draft, { draft = it }, Modifier.weight(1f), placeholder = { Text("Scrie medicului…") })
                IconButton(enabled = draft.isNotBlank(), onClick = {
                    val name = (patient as? Load.Ok)?.value?.name ?: "Pacient"
                    scope.launch {
                        try {
                            sent = app.api.sendMessage(name, draft.trim())
                            draft = ""
                            error = null
                        } catch (e: Exception) {
                            error = e.userMessage()
                        }
                    }
                }) { Icon(Icons.AutoMirrored.Filled.Send, "Trimite") }
            }
        }
    }
}

@Composable
private fun MessageBubble(message: Message) {
    val mine = message.authorRole == "patient"
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (mine) Arrangement.End else Arrangement.Start) {
        Column(
            Modifier.widthIn(max = 300.dp)
                .background(
                    if (mine) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant,
                    RoundedCornerShape(12.dp),
                )
                .padding(12.dp),
        ) {
            Text(message.authorName, style = MaterialTheme.typography.labelMedium)
            Text(message.text)
            Text(formatDate(message.created), style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
fun ExercisesScreen(onBack: () -> Unit, onPick: (Int) -> Unit) {
    BackScaffold("Alege exercițiul", onBack) { padding ->
        LazyColumn(Modifier.padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(Exercises.all, key = { it.id }) { e ->
                Card(Modifier.fillMaxWidth().clickable { onPick(e.id) }) {
                    Column(Modifier.padding(16.dp)) {
                        Text("${e.id}. ${e.name}", style = MaterialTheme.typography.titleMedium)
                        Text(e.description, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        }
    }
}

@Composable
fun SettingsScreen(app: AppContainer, onBack: () -> Unit) {
    var url by remember { mutableStateOf(app.settings.serverUrl) }
    var patientId by remember { mutableStateOf(app.settings.patientId.toString()) }
    var status by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    BackScaffold("Setări", onBack) { padding ->
        Column(Modifier.padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            OutlinedTextField(url, { url = it }, Modifier.fillMaxWidth(), label = { Text("Adresa serverului") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri), singleLine = true)
            Text("O vezi în consolă când pornești scripts/run_server.py pe laptop.", style = MaterialTheme.typography.bodySmall)
            OutlinedTextField(patientId, { patientId = it.filter(Char::isDigit) }, Modifier.fillMaxWidth(),
                label = { Text("Id pacient") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), singleLine = true)
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(onClick = {
                    app.settings.serverUrl = url
                    app.settings.patientId = patientId.toIntOrNull() ?: 1
                    status = "Salvat."
                }) { Text("Salvează") }
                OutlinedButton(onClick = {
                    app.settings.serverUrl = url
                    status = "Verific…"
                    scope.launch {
                        status = try {
                            "Conectat. Modelul de scor are eroarea tipică ±%.1f puncte.".format(app.api.health())
                        } catch (e: Exception) {
                            e.userMessage()
                        }
                    }
                }) { Text("Testează conexiunea") }
            }
            status?.let { Text(it) }
        }
    }
}
