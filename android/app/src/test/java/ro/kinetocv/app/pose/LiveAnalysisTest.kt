package ro.kinetocv.app.pose

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Locale

/**
 * Portarea din Python, verificată pe date de referință produse de codul Python
 * (src/features.py și src/reps.py), pe schelete și curbe sintetice.
 */
class LiveAnalysisTest {
    private fun resource(name: String) = javaClass.classLoader!!.getResource(name)!!.readText()

    @Test
    fun primaryAngleMatchesPython() {
        val rows = resource("angles.csv").trim().lines()
        assertEquals(300, rows.size)
        for (row in rows) {
            val values = row.split(",")
            val exercise = values[0].toInt()
            val mirrored = values[1] == "1"
            val expected = values[2].toDouble()
            val world = FloatArray(Joints.VALUES) { values[3 + it].toFloat() }
            // Telefonul lucrează cu float (32 de biți), Python cu double: diferențe de ordinul 0,001°.
            assertEquals("Es$exercise", expected, primaryAngle(exercise, world, mirrored), 0.01)
        }
    }

    @Test
    fun repCounterMatchesPython() {
        for (line in resource("reps.csv").trim().lines()) {
            val (exercise, expected, series) = line.split(";")
            val counter = RepCounter(Exercises.byId(exercise.toInt()).prominence)
            series.split(",").forEachIndexed { i, v -> counter.update(if (v == "nan") Double.NaN else v.toDouble(), i / 30.0) }
            assertEquals("Es$exercise", expected.toInt(), counter.count)
        }
    }

    @Test
    fun oneEuroSmoothsNoiseButFollowsSteps() {
        val filter = OneEuroFilter()
        var last = 0.0
        for (i in 0 until 60) last = filter.filter(doubleArrayOf(if (i % 2 == 0) 0.01 else -0.01), i / 30.0)[0]
        assertTrue("tremuratul scade", kotlin.math.abs(last) < 0.01)
        for (i in 60 until 120) last = filter.filter(doubleArrayOf(1.0), i / 30.0)[0]
        assertEquals("ajunge la noua poziție", 1.0, last, 0.01)
    }

    @Test
    fun recorderWritesDotDecimalsAndNullFramesEvenInRomanianLocale() {
        val previous = Locale.getDefault()
        Locale.setDefault(Locale.forLanguageTag("ro"))
        try {
            val recorder = Recorder()
            val points = FloatArray(Joints.VALUES) { 0.5f }
            assertEquals(0.0, recorder.add(1000, points, points)!!, 1e-9)
            recorder.add(1033, null, null)
            assertEquals(null, recorder.add(1033, points, points)) // același timp: ignorat
            val json = recorder.toJson(1, false, "Test \"Phone\"")
            assertTrue(json.startsWith("{\"exercise\":1,\"mirrored\":false,\"device\":\"Test Phone\",\"frames\":[{\"t\":0.0,\"image\":[0.5,"))
            assertTrue(json.endsWith(",{\"t\":0.033}]}"))
            assertFalse(json.contains("0,5"))
        } finally {
            Locale.setDefault(previous)
        }
    }

    @Test
    fun frameJudgement() {
        val image = FloatArray(Joints.VALUES) { 0.5f }
        val world = FloatArray(Joints.VALUES) { 0.9f }
        image[Joints.SHOULDER_L * 4 + 1] = 0.3f; image[Joints.SHOULDER_R * 4 + 1] = 0.3f
        image[Joints.HIP_L * 4 + 1] = 0.6f; image[Joints.HIP_R * 4 + 1] = 0.6f
        assertEquals(FrameStatus.OK, judgeFrame(image, world))
        assertEquals(FrameStatus.MISSING, judgeFrame(null, null))
        world[Joints.HIP_L * 4 + 3] = 0.2f
        assertEquals(FrameStatus.LOW_VISIBILITY, judgeFrame(image, world))
        world[Joints.HIP_L * 4 + 3] = 0.9f
        image[Joints.SHOULDER_L * 4 + 1] = 0.8f; image[Joints.SHOULDER_R * 4 + 1] = 0.8f
        assertEquals(FrameStatus.UPSIDE_DOWN, judgeFrame(image, world))
    }
}
