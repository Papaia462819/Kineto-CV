package ro.kinetocv.app

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.mutableStateOf
import ro.kinetocv.app.data.Api
import ro.kinetocv.app.data.MockRepository
import ro.kinetocv.app.data.Settings
import ro.kinetocv.app.ui.KinetoApp
import ro.kinetocv.app.ui.theme.KinetoTheme
import ro.kinetocv.app.ui.theme.TextSize

/** Obiectele comune ale aplicației, create o singură dată. */
class AppContainer(context: Context) {
    val settings = Settings(context)
    val api = Api(settings)
    val repo = MockRepository()

    // Preferințele de afișare: stare Compose (ecranul se redesenează imediat), salvată și pe telefon.
    private val textSizeState = mutableStateOf(TextSize.entries.getOrElse(settings.textSize) { TextSize.Normal })
    var textSize: TextSize
        get() = textSizeState.value
        set(value) {
            textSizeState.value = value
            settings.textSize = value.ordinal
        }

    private val voiceState = mutableStateOf(settings.voice)
    var voice: Boolean
        get() = voiceState.value
        set(value) {
            voiceState.value = value
            settings.voice = value
        }
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val app = AppContainer(applicationContext)
        setContent {
            KinetoTheme(textSize = app.textSize) {
                KinetoApp(app)
            }
        }
    }
}
