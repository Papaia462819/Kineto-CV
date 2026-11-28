package ro.kinetocv.app.ui

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.AspectRatioStrategy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Cameraswitch
import androidx.compose.material.icons.rounded.Flip
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Stop
import androidx.compose.material.icons.rounded.Videocam
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.style.TextAlign
import ro.kinetocv.app.ui.components.IconBubble
import ro.kinetocv.app.ui.components.PrimaryButton
import ro.kinetocv.app.ui.components.SecondaryButton
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ro.kinetocv.app.AppContainer
import ro.kinetocv.app.data.Api
import ro.kinetocv.app.data.Session
import ro.kinetocv.app.data.userMessage
import ro.kinetocv.app.pose.Exercise
import ro.kinetocv.app.pose.Exercises
import ro.kinetocv.app.pose.FrameStatus
import ro.kinetocv.app.pose.LiveAnalyzer
import ro.kinetocv.app.pose.PoseFrame
import ro.kinetocv.app.pose.PoseTracker
import ro.kinetocv.app.pose.Recorder
import ro.kinetocv.app.pose.judgeFrame
import java.util.Locale
import java.util.concurrent.Executors
import kotlin.math.min

private val BONES = listOf(11 to 12, 11 to 13, 13 to 15, 12 to 14, 14 to 16, 11 to 23, 12 to 24, 23 to 24,
    23 to 25, 25 to 27, 24 to 26, 26 to 28)
private val LEFT = listOf(11, 13, 15, 23, 25, 27)
private val RIGHT = listOf(12, 14, 16, 24, 26, 28)
private const val MIN_FRAMES = 30
private const val REP_BANNER_MS = 2000L
private const val FEEDBACK_MS = 3500L

/** Ce afișează ecranul live; se actualizează la fiecare cadru procesat. */
data class LiveUi(
    val status: FrameStatus = FrameStatus.MISSING,
    val angle: Double = Double.NaN,
    val reps: Int = 0,
    val seconds: Double = 0.0,
    val landmarks: FloatArray? = null,
    val width: Int = 0,
    val height: Int = 0,
    val fps: Double = 0.0,
    val banner: String? = null,
    val bannerUntil: Long = 0,
    val countdown: Double? = null, // secundele rămase din numărătoare
    val feedback: String? = null, // ultimul mesaj de corectare, afișat mare câteva secunde
    val feedbackUntil: Long = 0,
)

enum class Phase { Preview, Recording, Uploading, Failed }

/**
 * Leagă camera, MediaPipe, partea live și înregistrarea. Cadrele vin pe firul MediaPipe;
 * starea pentru ecran se publică pe firul principal (Compose o citește de acolo).
 */
class RecordController(context: Context, val exercise: Exercise, private val voiceOn: Boolean) : AutoCloseable {
    var phase by mutableStateOf(Phase.Preview)
        private set
    var ui by mutableStateOf(LiveUi())
        private set
    var error by mutableStateOf<String?>(null)
        private set
    var useFront by mutableStateOf(true)
    var mirrored by mutableStateOf(false)

    private val main = Handler(Looper.getMainLooper())
    val executor = Executors.newSingleThreadExecutor()!!
    val tracker = PoseTracker(context, ::onFrame) { message -> main.post { error = message } }

    @Volatile private var recorder: Recorder? = null
    @Volatile private var live: LiveAnalyzer? = null
    private var pendingJson: String? = null // păstrat ca să poți retrimite dacă rețeaua a căzut
    private var lastFrameMs = 0L
    private var fps = 0.0
    private val rulesJson = context.assets.open("feedback.json").bufferedReader(Charsets.UTF_8).use { it.readText() }
    private var summary: Map<String, Int> = emptyMap()

    // Vocea: pacientul stă la 2–3 m de telefon și nu poate citi ecranul, deci mesajele se și spun.
    private var voiceReady = false
    private val voice: TextToSpeech = TextToSpeech(context) { status ->
        if (status == TextToSpeech.SUCCESS) {
            val romanian = voice.setLanguage(Locale.forLanguageTag("ro-RO"))
            voiceReady = romanian != TextToSpeech.LANG_MISSING_DATA && romanian != TextToSpeech.LANG_NOT_SUPPORTED
            if (!voiceReady && voiceOn) main.post { error = "Vocea în română nu e instalată: mesajele apar doar pe ecran." }
        }
    }

    private fun say(text: String) {
        if (voiceReady && voiceOn) voice.speak(text, TextToSpeech.QUEUE_FLUSH, null, text)
    }

    fun start() {
        error = null
        summary = emptyMap()
        live = LiveAnalyzer(exercise, mirrored, rulesJson)
        recorder = Recorder()
        phase = Phase.Recording
        ui = ui.copy(reps = 0, seconds = 0.0, banner = null, feedback = null, countdown = LiveAnalyzer.COUNTDOWN_S)
        say("Stai nemișcat cinci secunde.")
    }

    fun cancel() {
        recorder = null
        live = null
        pendingJson = null
        phase = Phase.Preview
        ui = ui.copy(reps = 0, seconds = 0.0, banner = null, feedback = null, countdown = null)
        voice.stop()
    }

    /** Oprește înregistrarea, o trimite la server și întoarce sesiunea analizată (sau null dacă a eșuat). */
    suspend fun stopAndUpload(api: Api): Session? {
        val rec = recorder
        live?.let { summary = it.feedback.summary() }
        recorder = null
        live = null
        voice.stop()
        if (rec != null) {
            if (rec.size < MIN_FRAMES) {
                error = "Înregistrarea e prea scurtă."
                phase = Phase.Preview
                return null
            }
            val device = "${Build.MANUFACTURER} ${Build.MODEL}"
            val feedback = summary
            pendingJson = withContext(Dispatchers.Default) { rec.toJson(exercise.id, mirrored, device, feedback) }
        }
        val json = pendingJson ?: return null
        phase = Phase.Uploading
        return try {
            api.upload(json).also { pendingJson = null }
        } catch (e: Exception) {
            error = e.userMessage()
            phase = Phase.Failed
            null
        }
    }

    private fun onFrame(frame: PoseFrame) {
        val rec = recorder
        val analyzer = live
        var status = judgeFrame(frame.image, frame.world)
        var update: ro.kinetocv.app.pose.LiveUpdate? = null
        var seconds = 0.0
        if (rec != null && analyzer != null) {
            val t = rec.add(frame.timeMs, frame.image, frame.world)
            if (t != null) {
                update = analyzer.update(frame.image, frame.world, t)
                status = update.status
                seconds = t
            }
        }
        if (lastFrameMs > 0) fps = 0.9 * fps + 0.1 * 1000.0 / maxOf(1L, frame.timeMs - lastFrameMs)
        lastFrameMs = frame.timeMs
        val currentFps = fps
        main.post {
            if (phase != Phase.Recording && phase != Phase.Preview) return@post
            val now = System.currentTimeMillis()
            var next = ui.copy(status = status, landmarks = frame.image, width = frame.width, height = frame.height, fps = currentFps)
            if (update != null && phase == Phase.Recording) {
                if (ui.countdown != null && update.countdown == null) say("Începe exercițiul.")
                next = next.copy(angle = update.angle, reps = update.reps, seconds = seconds, countdown = update.countdown)
                update.newRep?.let { next = next.copy(banner = "Repetarea ${update.reps}: %.0f°".format(it.amplitude), bannerUntil = now + REP_BANNER_MS) }
                update.feedback?.let {
                    next = next.copy(feedback = it, feedbackUntil = now + FEEDBACK_MS)
                    say(it)
                }
            }
            ui = next
        }
    }

    override fun close() {
        recorder = null
        voice.shutdown()
        // Pe același fir cu analiza: modelul se închide abia după ultimul cadru aflat în lucru.
        executor.execute { tracker.close() }
        executor.shutdown()
    }
}

@Composable
fun RecordScreen(app: AppContainer, exerciseId: Int, onBack: () -> Unit, onDone: (Session) -> Unit) {
    val context = LocalContext.current
    var hasCamera by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    val ask = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { hasCamera = it }
    LaunchedEffect(Unit) { if (!hasCamera) ask.launch(Manifest.permission.CAMERA) }
    if (!hasCamera) {
        Column(
            Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).safeDrawingPadding().padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            IconBubble(Icons.Rounded.Videocam, size = 96.dp)
            Text("Avem nevoie de cameră", style = MaterialTheme.typography.headlineSmall, textAlign = TextAlign.Center)
            Text("Camera urmărește mișcarea ta. Imaginile nu pleacă de pe telefon: la server ajung doar punctele corpului.",
                style = MaterialTheme.typography.bodyLarge, textAlign = TextAlign.Center)
            PrimaryButton("Permite camera", onClick = { ask.launch(Manifest.permission.CAMERA) }, icon = Icons.Rounded.Videocam)
            SecondaryButton("Înapoi", onClick = onBack, modifier = Modifier.fillMaxWidth())
        }
        return
    }

    val exercise = Exercises.byId(exerciseId)
    val controller = remember { RecordController(context.applicationContext, exercise, app.voice) }
    DisposableEffect(Unit) { onDispose { controller.close() } }
    val scope = rememberCoroutineScope()

    Box(Modifier.fillMaxSize().background(Color.Black)) {
        CameraPreview(controller)
        SkeletonOverlay(controller.ui, flipX = controller.useFront)
        Column(Modifier.fillMaxSize().safeDrawingPadding().padding(12.dp)) {
            LivePanel(controller)
            Box(Modifier.weight(1f))
            Controls(controller, onBack, onStop = {
                scope.launch { controller.stopAndUpload(app.api)?.let(onDone) }
            })
        }
        BigMessages(controller)
    }
}

@Composable
private fun CameraPreview(controller: RecordController) {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val previewView = remember {
        // FIT_CENTER: imaginea întreagă, fără tăieturi, ca scheletul desenat să cadă exact peste persoană.
        PreviewView(context).apply { scaleType = PreviewView.ScaleType.FIT_CENTER }
    }
    AndroidView({ previewView }, Modifier.fillMaxSize())
    DisposableEffect(controller.useFront) {
        val future = ProcessCameraProvider.getInstance(context)
        future.addListener({
            val provider = future.get()
            // Același raport 4:3 pentru previzualizare și analiză, ca punctele să se suprapună pe imagine.
            val ratio = ResolutionSelector.Builder().setAspectRatioStrategy(AspectRatioStrategy.RATIO_4_3_FALLBACK_AUTO_STRATEGY).build()
            val preview = Preview.Builder().setResolutionSelector(ratio).build().also { it.setSurfaceProvider(previewView.surfaceProvider) }
            val analysis = ImageAnalysis.Builder()
                .setResolutionSelector(ratio)
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST) // dacă modelul e ocupat, sare cadre vechi
                .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                .build()
                .also { it.setAnalyzer(controller.executor, controller.tracker) }
            val camera = if (controller.useFront) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA
            provider.unbindAll()
            provider.bindToLifecycle(owner, camera, preview, analysis)
        }, ContextCompat.getMainExecutor(context))
        onDispose { runCatching { future.get().unbindAll() } }
    }
}

@Composable
private fun SkeletonOverlay(ui: LiveUi, flipX: Boolean) {
    Canvas(Modifier.fillMaxSize()) {
        val points = ui.landmarks ?: return@Canvas
        if (ui.width == 0 || ui.height == 0) return@Canvas
        val scale = min(size.width / ui.width, size.height / ui.height)
        val left = (size.width - ui.width * scale) / 2
        val top = (size.height - ui.height * scale) / 2
        fun p(i: Int): Offset {
            val x = if (flipX) 1 - points[i * 4] else points[i * 4] // camera frontală apare în oglindă pe ecran
            return Offset(left + x * ui.width * scale, top + points[i * 4 + 1] * ui.height * scale)
        }
        val boneColor = if (ui.status == FrameStatus.OK) Color(0xFF50C850) else Color.Gray
        BONES.forEach { (a, b) -> drawLine(boneColor, p(a), p(b), strokeWidth = 8f) }
        LEFT.forEach { drawCircle(Color(0xFFE63C3C), 12f, p(it)) }
        RIGHT.forEach { drawCircle(Color(0xFF288CE6), 12f, p(it)) }
    }
}

/** Ce trebuie văzut de la 2–3 metri: numărătoarea și mesajul de corectare, mari. */
@Composable
private fun BigMessages(controller: RecordController) {
    val ui = controller.ui
    if (controller.phase != Phase.Recording) return
    val countdown = ui.countdown
    if (countdown != null) {
        Box(Modifier.fillMaxSize().background(Color(0x88000000)), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("${kotlin.math.ceil(countdown).toInt()}", color = Color.White, fontSize = 160.sp, fontWeight = FontWeight.Bold)
                Text("Stai nemișcat", color = Color(0xFFFFE082), fontSize = 30.sp, fontWeight = FontWeight.Bold)
                Text("Memorez poziția ta de start", color = Color.White, fontSize = 16.sp)
            }
        }
    } else if (ui.feedback != null && System.currentTimeMillis() < ui.feedbackUntil) {
        Box(Modifier.fillMaxSize().safeDrawingPadding().padding(bottom = 96.dp, start = 16.dp, end = 16.dp),
            contentAlignment = Alignment.BottomCenter) {
            Text(
                ui.feedback,
                color = Color(0xFFFFE082),
                fontSize = 30.sp,
                fontWeight = FontWeight.Bold,
                lineHeight = 36.sp,
                modifier = Modifier.background(Color(0xCC000000), RoundedCornerShape(16.dp)).padding(16.dp),
            )
        }
    }
}

@Composable
private fun LivePanel(controller: RecordController) {
    val ui = controller.ui
    Column(
        Modifier.fillMaxWidth().background(Color(0x99000000), RoundedCornerShape(12.dp)).padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Text("${controller.exercise.id}. ${controller.exercise.name}", color = Color.White, style = MaterialTheme.typography.titleMedium)
        when (controller.phase) {
            Phase.Preview -> {
                Text(controller.exercise.description, color = Color.White, style = MaterialTheme.typography.bodySmall)
                Text(if (ui.status == FrameStatus.OK) "Te văd. Apasă Start când ești gata." else ui.status.message,
                    color = if (ui.status == FrameStatus.OK) Color(0xFF8BE28B) else Color(0xFFFFB74D))
                Text("Roșu = partea ta stângă. Dacă ridici mâna stângă și se mișcă punctele albastre, apasă „Oglindă”.",
                    color = Color.LightGray, style = MaterialTheme.typography.bodySmall)
            }
            Phase.Recording -> {
                Text("Înregistrez · %.0f s".format(ui.seconds), color = Color(0xFFFF8A80))
                Text("Repetări: ${ui.reps}", color = Color.White, fontSize = 34.sp, fontWeight = FontWeight.Bold)
                Text("Unghi (${controller.exercise.angleLabel}): " + (if (ui.angle.isNaN()) "–" else "%.0f°".format(ui.angle)),
                    color = Color.White)
                if (ui.status != FrameStatus.OK) Text(ui.status.message, color = Color(0xFFFFB74D))
                if (ui.banner != null && System.currentTimeMillis() < ui.bannerUntil) {
                    Text(ui.banner, color = Color(0xFFFFE082), fontWeight = FontWeight.Bold)
                }
            }
            Phase.Uploading -> Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                CircularProgressIndicator(color = Color.White)
                Text("Trimit punctele la server pentru analiză…", color = Color.White)
            }
            Phase.Failed -> Text("Trimiterea a eșuat.", color = Color(0xFFFF8A80))
        }
        controller.error?.let { Text(it, color = Color(0xFFFF8A80), style = MaterialTheme.typography.bodySmall) }
        Text("%.0f cadre/s".format(ui.fps), color = Color.Gray, style = MaterialTheme.typography.labelSmall)
    }
}

@Composable
private fun Controls(controller: RecordController, onBack: () -> Unit, onStop: () -> Unit) {
    val light = ButtonDefaults.outlinedButtonColors(contentColor = Color.White)
    val outline = BorderStroke(1.dp, Color.White.copy(alpha = 0.7f))
    val shape = MaterialTheme.shapes.medium
    val tall = Modifier.heightIn(min = 60.dp)
    val big = MaterialTheme.typography.labelLarge.copy(fontSize = 18.sp)
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        when (controller.phase) {
            Phase.Preview -> {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    ToolButton(Icons.Rounded.Cameraswitch, if (controller.useFront) "Camera spate" else "Camera față", Modifier.weight(1f)) {
                        controller.useFront = !controller.useFront
                    }
                    ToolButton(Icons.Rounded.Flip, "Oglindă: " + if (controller.mirrored) "da" else "nu", Modifier.weight(1f)) {
                        controller.mirrored = !controller.mirrored
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedButton(onClick = onBack, modifier = tall, colors = light, border = outline, shape = shape) { Text("Înapoi", style = big) }
                    Button(onClick = controller::start, modifier = tall.weight(1f), shape = shape) {
                        Icon(Icons.Rounded.PlayArrow, null, Modifier.size(28.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("Start", style = big)
                    }
                }
            }
            Phase.Recording -> Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick = controller::cancel, modifier = tall, colors = light, border = outline, shape = shape) {
                    Text("Renunță", style = big)
                }
                Button(onClick = onStop, modifier = tall.weight(1f), shape = shape,
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFC62828), contentColor = Color.White)) {
                    Icon(Icons.Rounded.Stop, null, Modifier.size(28.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("Gata, trimite", style = big)
                }
            }
            Phase.Uploading -> {}
            Phase.Failed -> Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick = controller::cancel, modifier = tall, colors = light, border = outline, shape = shape) {
                    Text("Renunță", style = big)
                }
                Button(onClick = onStop, modifier = tall.weight(1f), shape = shape) {
                    Icon(Icons.Rounded.Refresh, null, Modifier.size(26.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("Retrimite", style = big)
                }
            }
        }
    }
}

/** Buton mic de reglaj peste imaginea camerei (camera, oglinda). */
@Composable
private fun ToolButton(icon: ImageVector, text: String, modifier: Modifier, onClick: () -> Unit) {
    Surface(onClick = onClick, modifier = modifier.heightIn(min = 52.dp), shape = CircleShape, color = Color(0x99000000),
        contentColor = Color.White, border = BorderStroke(1.dp, Color.White.copy(alpha = 0.4f))) {
        Row(Modifier.padding(horizontal = 14.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center) {
            Icon(icon, null, Modifier.size(22.dp))
            Spacer(Modifier.width(8.dp))
            Text(text, style = MaterialTheme.typography.labelLarge, maxLines = 1)
        }
    }
}
