package ro.kinetocv.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.CancellationException
import ro.kinetocv.app.data.userMessage
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

val Teal = Color(0xFF00796B)
val Good = Color(0xFF2E7D32)
val Medium = Color(0xFFF9A825)
val Weak = Color(0xFFC62828)

@Composable
fun KinetoTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = lightColorScheme(primary = Teal, secondary = Color(0xFF455A64), tertiary = Color(0xFF5D4037)),
        content = content,
    )
}

/** Starea unei încărcări de pe server. */
sealed interface Load<out T> {
    data object Loading : Load<Nothing>
    data class Ok<T>(val value: T) : Load<T>
    data class Failed(val message: String) : Load<Nothing>
}

/** Încarcă ceva de pe server când ecranul apare; întoarce starea și o funcție de reîncărcare. */
@Composable
fun <T> rememberLoad(key: Any?, block: suspend () -> T): Pair<Load<T>, () -> Unit> {
    var version by remember { mutableIntStateOf(0) }
    var state by remember(key) { mutableStateOf<Load<T>>(Load.Loading) }
    LaunchedEffect(key, version) {
        state = try {
            Load.Ok(block())
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Load.Failed(e.userMessage())
        }
    }
    return state to { version++ }
}

private val romanian: Locale = Locale.forLanguageTag("ro")

/** "2026-11-18T18:00:00" → "18 nov. 2026, 18:00" */
fun formatDate(iso: String): String = runCatching {
    LocalDateTime.parse(iso).format(DateTimeFormatter.ofPattern("d MMM yyyy, HH:mm", romanian))
}.getOrDefault(iso)

fun scoreColor(score: Double?) = when {
    score == null -> Color.Gray
    score >= 40 -> Good
    score >= 30 -> Medium
    else -> Weak
}

@Composable
fun ScoreBadge(score: Double?, size: Int = 52) {
    Box(
        Modifier.size(size.dp).background(scoreColor(score), CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        Text(score?.let { "%.0f".format(it) } ?: "–", color = Color.White, fontWeight = FontWeight.Bold, fontSize = (size / 2.6).sp)
    }
}

@Composable
fun LoadingRow() {
    Row(Modifier.fillMaxWidth().padding(24.dp), horizontalArrangement = Arrangement.Center) { CircularProgressIndicator() }
}

@Composable
fun ErrorCard(message: String, onRetry: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text(message, color = MaterialTheme.colorScheme.onErrorContainer)
            TextButton(onClick = onRetry) { Text("Încearcă din nou") }
        }
    }
}

@Composable
fun SectionTitle(text: String) {
    Text(text, style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 8.dp))
}
