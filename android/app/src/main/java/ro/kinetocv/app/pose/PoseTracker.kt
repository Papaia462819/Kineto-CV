package ro.kinetocv.app.pose

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Matrix
import android.os.SystemClock
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import com.google.mediapipe.framework.image.BitmapImageBuilder
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.vision.core.RunningMode
import com.google.mediapipe.tasks.vision.poselandmarker.PoseLandmarker
import com.google.mediapipe.tasks.vision.poselandmarker.PoseLandmarkerResult

/**
 * Un cadru procesat de MediaPipe: aceleași două matrice ca în Python (src/pose.py), aplatizate la 132 de valori.
 * image: x, y în 0–1 față de imaginea rotită drept, z, vizibilitate. world: metri, față de mijlocul șoldurilor.
 */
class PoseFrame(val timeMs: Long, val image: FloatArray?, val world: FloatArray?, val width: Int, val height: Int)

/**
 * Primește imaginile camerei (CameraX) și le dă lui MediaPipe în modul LIVE_STREAM.
 * Imaginea NU se întoarce în oglindă: modelul vede scena ca o cameră obișnuită, la fel ca pe laptop
 * (mirrored = false). Doar previzualizarea camerei frontale apare în oglindă pe ecran.
 */
class PoseTracker(
    context: Context,
    private val onFrame: (PoseFrame) -> Unit,
    private val onError: (String) -> Unit,
) : ImageAnalysis.Analyzer, AutoCloseable {

    private val landmarker: PoseLandmarker
    private var lastTimestamp = 0L
    @Volatile private var lastSize = 0 to 0

    init {
        val options = PoseLandmarker.PoseLandmarkerOptions.builder()
            .setBaseOptions(BaseOptions.builder().setModelAssetPath(MODEL).build())
            .setRunningMode(RunningMode.LIVE_STREAM)
            .setNumPoses(1)
            .setResultListener { result: PoseLandmarkerResult, _ -> handle(result) }
            .setErrorListener { e -> onError(e.message ?: "eroare MediaPipe") }
            .build()
        landmarker = PoseLandmarker.createFromOptions(context, options)
    }

    override fun analyze(proxy: ImageProxy) {
        // LIVE_STREAM cere timpi strict crescători, în milisecunde.
        val timestamp = maxOf(SystemClock.uptimeMillis(), lastTimestamp + 1)
        lastTimestamp = timestamp
        val rotation = proxy.imageInfo.rotationDegrees
        val bitmap = proxy.toBitmap()
        proxy.close()
        // Senzorul camerei e montat culcat: rotim imaginea ca persoana să fie în picioare.
        val upright = if (rotation == 0) bitmap else
            Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, Matrix().apply { postRotate(rotation.toFloat()) }, true)
        lastSize = upright.width to upright.height
        landmarker.detectAsync(BitmapImageBuilder(upright).build(), timestamp)
    }

    private fun handle(result: PoseLandmarkerResult) {
        val (width, height) = lastSize
        val landmarks = result.landmarks().firstOrNull()
        val world = result.worldLandmarks().firstOrNull()
        if (landmarks == null || world == null || landmarks.size < 33 || world.size < 33) {
            onFrame(PoseFrame(result.timestampMs(), null, null, width, height))
            return
        }
        val image = FloatArray(Joints.VALUES)
        val meters = FloatArray(Joints.VALUES)
        for (i in 0 until 33) {
            val p = landmarks[i]
            val w = world[i]
            val visibility = p.visibility().orElse(0f)
            image[i * 4] = p.x(); image[i * 4 + 1] = p.y(); image[i * 4 + 2] = p.z(); image[i * 4 + 3] = visibility
            meters[i * 4] = w.x(); meters[i * 4 + 1] = w.y(); meters[i * 4 + 2] = w.z()
            meters[i * 4 + 3] = w.visibility().orElse(visibility)
        }
        onFrame(PoseFrame(result.timestampMs(), image, meters, width, height))
    }

    override fun close() = landmarker.close()

    companion object {
        const val MODEL = "pose_landmarker_full.task" // copiat din ../models la build (vezi app/build.gradle.kts)
    }
}
