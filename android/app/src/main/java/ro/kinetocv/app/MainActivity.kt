package ro.kinetocv.app

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import ro.kinetocv.app.data.Api
import ro.kinetocv.app.data.Settings
import ro.kinetocv.app.ui.KinetoApp
import ro.kinetocv.app.ui.KinetoTheme

/** Obiectele comune ale aplicației, create o singură dată. */
class AppContainer(context: Context) {
    val settings = Settings(context)
    val api = Api(settings)
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val app = AppContainer(applicationContext)
        setContent {
            KinetoTheme {
                KinetoApp(app)
            }
        }
    }
}
