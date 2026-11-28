package ro.kinetocv.app.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Accessibility
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Forum
import androidx.compose.material.icons.rounded.MedicalInformation
import androidx.compose.material.icons.rounded.Person
import androidx.compose.material.icons.rounded.RecordVoiceOver
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material.icons.rounded.Smartphone
import androidx.compose.material.icons.rounded.Wifi
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import ro.kinetocv.app.AppContainer
import ro.kinetocv.app.data.userMessage
import ro.kinetocv.app.ui.Navigator
import ro.kinetocv.app.ui.Screen
import ro.kinetocv.app.ui.Tab
import ro.kinetocv.app.ui.TabColumn
import ro.kinetocv.app.ui.components.AppCard
import ro.kinetocv.app.ui.components.Avatar
import ro.kinetocv.app.ui.components.DetailScaffold
import ro.kinetocv.app.ui.components.ExercisePictogram
import ro.kinetocv.app.ui.components.IconBubble
import ro.kinetocv.app.ui.components.ListRow
import ro.kinetocv.app.ui.components.PrimaryButton
import ro.kinetocv.app.ui.components.ScreenHeader
import ro.kinetocv.app.ui.components.SecondaryButton
import ro.kinetocv.app.ui.components.SectionHeader
import ro.kinetocv.app.ui.theme.Space
import ro.kinetocv.app.ui.theme.TextSize
import java.time.LocalDate

/** Profilul: datele pacientului (deocamdată demonstrative), afișarea și ajutorul. */
@Composable
fun ProfileTab(app: AppContainer, nav: Navigator, padding: PaddingValues) {
    val repo = app.repo
    val patient = repo.patient
    TabColumn(padding) {
        item { ScreenHeader("Profilul meu") }
        item {
            AppCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Avatar(repo.initials, size = 72.dp, container = MaterialTheme.colorScheme.primaryContainer,
                        content = MaterialTheme.colorScheme.onPrimaryContainer)
                    Spacer(Modifier.width(16.dp))
                    Column {
                        Text(patient.name, style = MaterialTheme.typography.headlineSmall)
                        patient.birthYear?.let {
                            Text("${LocalDate.now().year - it} de ani", style = MaterialTheme.typography.bodyLarge,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                patient.diagnosis?.let { InfoLine(Icons.Rounded.MedicalInformation, "Diagnostic", it) }
                patient.therapist?.let { InfoLine(Icons.Rounded.Person, "Medicul meu", it) }
            }
        }

        item { SectionHeader("Afișare și sunet") }
        item {
            AppCard {
                Text("Mărimea textului", style = MaterialTheme.typography.titleMedium)
                Row(Modifier.selectableGroup().height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    TextSize.entries.forEach { size ->
                        TextSizeOption(size, selected = app.textSize == size, Modifier.weight(1f).fillMaxHeight()) { app.textSize = size }
                    }
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Row(
                    Modifier.toggleable(app.voice, role = Role.Switch) { app.voice = it }.heightIn(min = 56.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    IconBubble(Icons.Rounded.RecordVoiceOver)
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)) {
                        Text("Ghid vocal", style = MaterialTheme.typography.titleMedium)
                        Text("Îți spune cu voce ce să corectezi", style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Switch(checked = app.voice, onCheckedChange = null)
                }
            }
        }

        item { SectionHeader("Ajutor") }
        item {
            AppCard(padding = PaddingValues(vertical = 4.dp)) {
                ListRow("Cum mă așez în fața camerei", leading = { IconBubble(Icons.Rounded.Accessibility) }) { nav.open(Screen.Guide) }
                HorizontalDivider(Modifier.padding(horizontal = 16.dp), color = MaterialTheme.colorScheme.outlineVariant)
                ListRow("Scrie medicului", leading = { IconBubble(Icons.Rounded.Forum) }) { nav.goTo(Tab.Doctor) }
            }
        }

        item { SectionHeader("Avansat") }
        item {
            AppCard(padding = PaddingValues(vertical = 4.dp)) {
                ListRow(
                    "Conexiunea cu serverul",
                    subtitle = "Pentru persoana care a instalat aplicația",
                    leading = {
                        IconBubble(Icons.Rounded.Settings, container = MaterialTheme.colorScheme.surfaceContainerHigh,
                            tint = MaterialTheme.colorScheme.onSurfaceVariant)
                    },
                ) { nav.open(Screen.TechSettings) }
            }
        }
        item {
            Text("Kineto-CV 0.1 · date demonstrative", style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
        }
    }
}

@Composable
private fun InfoLine(icon: ImageVector, label: String, value: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, Modifier.size(26.dp), tint = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.width(14.dp))
        Column {
            Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(value, style = MaterialTheme.typography.bodyLarge)
        }
    }
}

/** O variantă de mărime a textului: litera „A” desenată la mărimea ei, ca alegerea să se vadă. */
@Composable
private fun TextSizeOption(size: TextSize, selected: Boolean, modifier: Modifier, onClick: () -> Unit) {
    val colors = MaterialTheme.colorScheme
    Surface(
        modifier.selectable(selected, role = Role.RadioButton, onClick = onClick),
        shape = MaterialTheme.shapes.medium,
        color = if (selected) colors.primaryContainer else colors.surfaceContainerLow,
        border = BorderStroke(if (selected) 2.dp else 1.dp, if (selected) colors.primary else colors.outlineVariant),
    ) {
        Box {
            Column(Modifier.fillMaxSize().padding(vertical = 14.dp, horizontal = 4.dp), horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Bottom) {
                // Litera nu crește cu setarea, ca cele trei variante să rămână comparabile.
                Text("A", fontSize = with(LocalDensity.current) { (24 * size.factor).dp.toSp() }, fontWeight = FontWeight.Bold,
                    color = if (selected) colors.onPrimaryContainer else colors.onSurface)
                Text(size.label, style = MaterialTheme.typography.labelMedium, textAlign = TextAlign.Center,
                    color = if (selected) colors.onPrimaryContainer else colors.onSurfaceVariant)
            }
            if (selected) {
                Icon(Icons.Rounded.CheckCircle, null, Modifier.align(Alignment.TopEnd).padding(6.dp).size(20.dp), tint = colors.primary)
            }
        }
    }
}

/** Pagina de ajutor: cum se așază telefonul și persoana. */
@Composable
fun GuideScreen(nav: Navigator) {
    DetailScaffold("Cum mă așez", nav.back) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(horizontal = Space.screen, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(Space.gap),
        ) {
            AppCard {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceEvenly) {
                    IconBubble(Icons.Rounded.Smartphone, size = 64.dp)
                    Text("← 2–3 m →", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
                    ExercisePictogram(0, size = 96.dp)
                }
                Text("Așază telefonul în picioare, sprijinit, cu camera spre tine. Apoi fă câțiva pași înapoi până te vezi întreg pe ecran.",
                    style = MaterialTheme.typography.bodyLarge)
            }
            PreparationCard()
            SafetyNote()
        }
    }
}

/** Setările tehnice (adresa serverului). Le folosește doar cine instalează aplicația. */
@Composable
fun TechSettingsScreen(app: AppContainer, nav: Navigator) {
    var url by remember { mutableStateOf(app.settings.serverUrl) }
    var patientId by remember { mutableStateOf(app.settings.patientId.toString()) }
    var status by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    DetailScaffold("Conexiunea cu serverul", nav.back) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(horizontal = Space.screen, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(Space.gap),
        ) {
            AppCard {
                OutlinedTextField(url, { url = it }, Modifier.fillMaxWidth(), label = { Text("Adresa serverului") },
                    textStyle = MaterialTheme.typography.bodyLarge,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri), singleLine = true)
                Text("O vezi în consolă când pornești scripts/run_server.py pe laptop.", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                OutlinedTextField(patientId, { patientId = it.filter(Char::isDigit) }, Modifier.fillMaxWidth(),
                    label = { Text("Id pacient pe server") }, textStyle = MaterialTheme.typography.bodyLarge,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), singleLine = true)
            }
            PrimaryButton("Salvează", onClick = {
                app.settings.serverUrl = url
                app.settings.patientId = patientId.toIntOrNull() ?: 1
                status = "Salvat."
            })
            SecondaryButton("Testează conexiunea", modifier = Modifier.fillMaxWidth(), icon = Icons.Rounded.Wifi, onClick = {
                app.settings.serverUrl = url
                status = "Verific…"
                scope.launch {
                    status = try {
                        "Conectat. Modelul de scor are eroarea tipică ±%.1f puncte.".format(app.api.health())
                    } catch (e: Exception) {
                        e.userMessage()
                    }
                }
            })
            status?.let { Text(it, style = MaterialTheme.typography.bodyLarge) }
        }
    }
}
