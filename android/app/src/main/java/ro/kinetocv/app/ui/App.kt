package ro.kinetocv.app.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsTopHeight
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.calculateEndPadding
import androidx.compose.foundation.layout.calculateStartPadding
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.FitnessCenter
import androidx.compose.material.icons.outlined.Forum
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Insights
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.rounded.FitnessCenter
import androidx.compose.material.icons.rounded.Forum
import androidx.compose.material.icons.rounded.Home
import androidx.compose.material.icons.rounded.Insights
import androidx.compose.material.icons.rounded.Person
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.unit.dp
import ro.kinetocv.app.AppContainer
import ro.kinetocv.app.ui.screens.DoctorTab
import ro.kinetocv.app.ui.screens.ExerciseDetailScreen
import ro.kinetocv.app.ui.screens.ExercisesTab
import ro.kinetocv.app.ui.screens.GuideScreen
import ro.kinetocv.app.ui.screens.HomeTab
import ro.kinetocv.app.ui.screens.ProfileTab
import ro.kinetocv.app.ui.screens.ProgressTab
import ro.kinetocv.app.ui.screens.SessionDetailScreen
import ro.kinetocv.app.ui.screens.TechSettingsScreen
import ro.kinetocv.app.ui.theme.Space

/** Taburile din bara de jos: puține, cu iconiță și nume, mereu în același loc. */
enum class Tab(val label: String, val icon: ImageVector, val selectedIcon: ImageVector) {
    Home("Acasă", Icons.Outlined.Home, Icons.Rounded.Home),
    Exercises("Exerciții", Icons.Outlined.FitnessCenter, Icons.Rounded.FitnessCenter),
    Progress("Progres", Icons.Outlined.Insights, Icons.Rounded.Insights),
    Doctor("Medic", Icons.Outlined.Forum, Icons.Rounded.Forum),
    Profile("Profil", Icons.Outlined.Person, Icons.Rounded.Person),
}

/** Ecranele care se deschid peste taburi (au butonul „Înapoi”). */
sealed interface Screen {
    data class ExerciseDetail(val exercise: Int) : Screen
    data class SessionDetail(val id: Int, val justRecorded: Boolean = false) : Screen
    data class Record(val exercise: Int) : Screen
    data object TechSettings : Screen
    data object Guide : Screen
}

/** Ce poate face un ecran: deschide un detaliu, trece la alt tab, se întoarce. */
class Navigator(val open: (Screen) -> Unit, val goTo: (Tab) -> Unit, val back: () -> Unit)

@Composable
fun KinetoApp(app: AppContainer) {
    var tab by rememberSaveable { mutableStateOf(Tab.Home) }
    var stack by remember { mutableStateOf(listOf<Screen>()) }
    val nav = remember {
        Navigator(
            open = { stack = stack + it },
            goTo = { tab = it; stack = emptyList() },
            back = { stack = stack.dropLast(1) },
        )
    }
    BackHandler(enabled = stack.isNotEmpty() || tab != Tab.Home) {
        if (stack.isNotEmpty()) stack = stack.dropLast(1) else tab = Tab.Home
    }
    LaunchedEffect(tab) { if (tab == Tab.Doctor) app.repo.markRead() }

    // Păstrează poziția de derulare a fiecărui tab cât timp e deschis un detaliu.
    val saved = rememberSaveableStateHolder()
    when (val screen = stack.lastOrNull()) {
        null -> MainTabs(app, tab, onTab = { tab = it }) { padding ->
            saved.SaveableStateProvider(tab.name) {
                when (tab) {
                    Tab.Home -> HomeTab(app, nav, padding)
                    Tab.Exercises -> ExercisesTab(app, nav, padding)
                    Tab.Progress -> ProgressTab(app, nav, padding)
                    Tab.Doctor -> DoctorTab(app, padding)
                    Tab.Profile -> ProfileTab(app, nav, padding)
                }
            }
        }
        is Screen.ExerciseDetail -> ExerciseDetailScreen(app, screen.exercise, nav)
        is Screen.SessionDetail -> SessionDetailScreen(app, screen.id, screen.justRecorded, nav)
        is Screen.Record -> RecordScreen(app, screen.exercise, nav.back) { session ->
            // Sesiunea nouă intră în istoric, iar rezultatul înlocuiește camera: „înapoi” nu duce la cameră.
            app.repo.addSession(session)
            stack = stack.dropLast(1) + Screen.SessionDetail(session.id, justRecorded = true)
        }
        Screen.TechSettings -> TechSettingsScreen(app, nav)
        Screen.Guide -> GuideScreen(nav)
    }
}

@Composable
private fun MainTabs(app: AppContainer, tab: Tab, onTab: (Tab) -> Unit, content: @Composable (PaddingValues) -> Unit) {
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        // Bandă opacă sub bara de stare: conținutul derulat nu trece pe sub ceas și baterie.
        topBar = {
            Spacer(Modifier.fillMaxWidth().windowInsetsTopHeight(WindowInsets.statusBars).background(MaterialTheme.colorScheme.background))
        },
        bottomBar = {
            Column {
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                // Etichetele cresc cu textul doar până la o limită, altfel „Exerciții” nu mai încape pe 5 coloane.
                val density = LocalDensity.current
                val labelSize = with(density) { (15f * minOf(density.fontScale, 1.1f)).dp.toSp() }
                NavigationBar(containerColor = MaterialTheme.colorScheme.surfaceContainerLowest, tonalElevation = 0.dp) {
                    Tab.entries.forEach { t ->
                        val selected = t == tab
                        NavigationBarItem(
                            selected = selected,
                            onClick = { onTab(t) },
                            icon = {
                                BadgedBox(badge = {
                                    if (t == Tab.Doctor && app.repo.unread > 0) Badge { Text("${app.repo.unread}") }
                                }) {
                                    Icon(if (selected) t.selectedIcon else t.icon, null, Modifier.size(28.dp))
                                }
                            },
                            label = { Text(t.label, style = MaterialTheme.typography.labelMedium, fontSize = labelSize, maxLines = 1, softWrap = false) },
                            colors = NavigationBarItemDefaults.colors(
                                indicatorColor = MaterialTheme.colorScheme.primaryContainer,
                                selectedIconColor = MaterialTheme.colorScheme.onPrimaryContainer,
                                selectedTextColor = MaterialTheme.colorScheme.primary,
                                unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                                unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
                            ),
                        )
                    }
                }
            }
        },
        content = content,
    )
}

/** Lista derulabilă a unui tab, cu marginile comune tuturor taburilor. */
@Composable
fun TabColumn(padding: PaddingValues, content: LazyListScope.() -> Unit) {
    val dir = LocalLayoutDirection.current
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(
            start = padding.calculateStartPadding(dir) + Space.screen,
            end = padding.calculateEndPadding(dir) + Space.screen,
            top = padding.calculateTopPadding() + 12.dp,
            bottom = padding.calculateBottomPadding() + 28.dp,
        ),
        verticalArrangement = Arrangement.spacedBy(Space.gap),
        content = content,
    )
}
