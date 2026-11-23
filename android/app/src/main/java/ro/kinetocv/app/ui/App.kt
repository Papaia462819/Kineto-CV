package ro.kinetocv.app.ui

import androidx.activity.compose.BackHandler
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import ro.kinetocv.app.AppContainer

/** Ecranele aplicației. Navigarea e o stivă simplă: ultimul ecran din listă e cel afișat. */
sealed interface Screen {
    data object Home : Screen
    data class SessionDetail(val id: Int, val justRecorded: Boolean = false) : Screen
    data object Messages : Screen
    data object Exercises : Screen
    data class Record(val exercise: Int) : Screen
    data object Settings : Screen
}

@Composable
fun KinetoApp(app: AppContainer) {
    var stack by remember { mutableStateOf(listOf<Screen>(Screen.Home)) }
    val open: (Screen) -> Unit = { stack = stack + it }
    val back: () -> Unit = { if (stack.size > 1) stack = stack.dropLast(1) }
    BackHandler(enabled = stack.size > 1, onBack = back)

    when (val screen = stack.last()) {
        Screen.Home -> HomeScreen(app, open)
        is Screen.SessionDetail -> SessionScreen(app, screen.id, screen.justRecorded, back)
        Screen.Messages -> MessagesScreen(app, back)
        Screen.Exercises -> ExercisesScreen(back) { stack = stack.dropLast(1) + Screen.Record(it) }
        is Screen.Record -> RecordScreen(app, screen.exercise, back) { id ->
            // După încărcare, înregistrarea e înlocuită de rezultat: „înapoi” duce acasă, nu la cameră.
            stack = stack.dropLast(1) + Screen.SessionDetail(id, justRecorded = true)
        }
        Screen.Settings -> SettingsScreen(app, back)
    }
}
