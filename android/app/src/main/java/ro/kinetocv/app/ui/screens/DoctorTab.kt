package ro.kinetocv.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material.icons.rounded.Videocam
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.SuggestionChipDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import ro.kinetocv.app.AppContainer
import ro.kinetocv.app.data.Message
import ro.kinetocv.app.data.MockRepository
import ro.kinetocv.app.ui.appointmentDate
import ro.kinetocv.app.ui.components.AppCard
import ro.kinetocv.app.ui.components.Avatar
import ro.kinetocv.app.ui.components.IconBubble
import ro.kinetocv.app.ui.components.ScreenHeader
import ro.kinetocv.app.ui.relativeDayTime
import ro.kinetocv.app.ui.theme.Space

private val QUICK_REPLIES = listOf("Totul e în regulă", "Am terminat exercițiile", "Simt durere", "Am o întrebare")

/** Legătura cu medicul: cine e, când e următoarea consultație și firul de mesaje. */
@Composable
fun DoctorTab(app: AppContainer, padding: PaddingValues) {
    val repo = app.repo
    var draft by rememberSaveable { mutableStateOf("") }
    val list = rememberLazyListState()
    val header = 2 // titlul și cardul medicului, înaintea mesajelor
    LaunchedEffect(repo.messages.size) { list.scrollToItem(header + repo.messages.size - 1) }

    Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).imePadding().clipToBounds()) {
        LazyColumn(
            Modifier.weight(1f),
            state = list,
            contentPadding = PaddingValues(horizontal = Space.screen, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item { ScreenHeader("Medicul meu") }
            item { DoctorCard(repo) }
            items(repo.messages, key = { it.id }) { MessageBubble(it) }
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        Surface(color = MaterialTheme.colorScheme.surfaceContainerLowest) {
            Column(Modifier.padding(vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(
                    Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = Space.screen),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    QUICK_REPLIES.forEach { reply ->
                        SuggestionChip(
                            onClick = { draft = reply },
                            label = { Text(reply, style = MaterialTheme.typography.labelLarge) },
                            modifier = Modifier.heightIn(min = 48.dp),
                            shape = CircleShape,
                            colors = SuggestionChipDefaults.suggestionChipColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
                        )
                    }
                }
                Row(Modifier.padding(horizontal = Space.screen), verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        draft, { draft = it },
                        Modifier.weight(1f).heightIn(min = 56.dp),
                        placeholder = { Text("Scrie un mesaj…", style = MaterialTheme.typography.bodyLarge) },
                        textStyle = MaterialTheme.typography.bodyLarge,
                        shape = RoundedCornerShape(28.dp),
                        maxLines = 4,
                        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                        colors = OutlinedTextFieldDefaults.colors(unfocusedBorderColor = MaterialTheme.colorScheme.outline),
                    )
                    Spacer(Modifier.width(10.dp))
                    FilledIconButton(
                        onClick = {
                            repo.sendMessage(draft.trim())
                            draft = ""
                        },
                        enabled = draft.isNotBlank(),
                        modifier = Modifier.size(56.dp),
                    ) { Icon(Icons.AutoMirrored.Rounded.Send, "Trimite", Modifier.size(26.dp)) }
                }
            }
        }
    }
}

@Composable
private fun DoctorCard(repo: MockRepository) {
    AppCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Avatar(repo.doctor.initials, size = 64.dp)
            Spacer(Modifier.width(16.dp))
            Column(Modifier.weight(1f)) {
                Text(repo.doctor.name, style = MaterialTheme.typography.titleLarge)
                Text(repo.doctor.role, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(repo.doctor.clinic, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Row(
            Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.tertiaryContainer, MaterialTheme.shapes.medium).padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconBubble(Icons.Rounded.Videocam, container = MaterialTheme.colorScheme.surfaceContainerLowest,
                tint = MaterialTheme.colorScheme.tertiary, size = 44.dp)
            Spacer(Modifier.width(12.dp))
            Column {
                Text("Următoarea consultație", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onTertiaryContainer)
                Text(appointmentDate(repo.appointment.time), style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onTertiaryContainer)
            }
        }
    }
}

@Composable
private fun MessageBubble(message: Message) {
    val mine = message.authorRole == "patient"
    val shape = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp, bottomStart = if (mine) 20.dp else 6.dp, bottomEnd = if (mine) 6.dp else 20.dp)
    Column(Modifier.fillMaxWidth(), horizontalAlignment = if (mine) Alignment.End else Alignment.Start) {
        val bubble = if (mine) {
            Modifier.background(MaterialTheme.colorScheme.primary, shape)
        } else {
            Modifier.background(MaterialTheme.colorScheme.surfaceContainerLowest, shape).border(1.dp, MaterialTheme.colorScheme.outlineVariant, shape)
        }
        Text(
            message.text,
            style = MaterialTheme.typography.bodyLarge,
            color = if (mine) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.widthIn(max = 300.dp).then(bubble).padding(horizontal = 16.dp, vertical = 12.dp),
        )
        Text(
            (if (mine) "Tu" else message.authorName) + " · " + relativeDayTime(message.created),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 4.dp, start = 6.dp, end = 6.dp),
        )
    }
}
