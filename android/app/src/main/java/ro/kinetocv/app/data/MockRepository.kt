package ro.kinetocv.app.data

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.setValue
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.temporal.TemporalAdjusters

data class Doctor(val name: String, val role: String, val clinic: String) {
    val initials get() = name.removePrefix("Dr. ").split(" ").mapNotNull { it.firstOrNull() }.take(2).joinToString("")
}

data class Appointment(val time: LocalDateTime, val title: String, val video: Boolean)

/**
 * Datele afișate în interfață, deocamdată inventate (pacient, plan, istoric, mesaje).
 * Sunt ținute în memorie: o sesiune înregistrată sau un mesaj trimis apar imediat, dar dispar la repornire.
 * Mai târziu, aceleași liste vor veni de la server (vezi [Api]).
 */
class MockRepository {
    private val today: LocalDate = LocalDate.now()

    val doctor = Doctor("Dr. Andrei Pop", "Kinetoterapeut", "Clinica de Recuperare Demo")

    val patient = Patient(
        id = 1,
        name = "Maria Ionescu",
        birthYear = 1968,
        diagnosis = "Lombalgie cronică",
        therapist = doctor.name,
        plan = listOf(PlanItem(1, 10, 3), PlanItem(2, 10, 3), PlanItem(5, 8, 3)),
    )

    val firstName get() = patient.name.substringBefore(" ")
    val initials get() = patient.name.split(" ").mapNotNull { it.firstOrNull() }.take(2).joinToString("")

    val appointment = Appointment(
        time = today.with(TemporalAdjusters.next(DayOfWeek.THURSDAY)).atTime(10, 0),
        title = "Consultație video de control",
        video = true,
    )

    /** Toate sesiunile, cele mai noi primele. */
    val sessions = mutableStateListOf<Session>().apply { addAll(demoSessions().sortedByDescending { it.created }) }

    /** Firul de mesaje, cele mai vechi primele. */
    val messages = mutableStateListOf<Message>().apply { addAll(demoMessages()) }

    /** Mesajele medicului necitite încă (bulina de pe tabul Medic). */
    var unread by mutableIntStateOf(1)
        private set

    fun markRead() {
        unread = 0
    }

    fun session(id: Int): Session? = sessions.firstOrNull { it.id == id }

    /** O sesiune nouă, primită de la server după înregistrare. */
    fun addSession(session: Session) {
        sessions.removeAll { it.id == session.id }
        sessions.add(0, session)
    }

    fun sendMessage(text: String) {
        val id = (messages.maxOfOrNull { it.id } ?: 0) + 1
        messages.add(Message(id, LocalDateTime.now().withNano(0).toString(), "patient", patient.name, text))
    }

    /** Sesiunile unui exercițiu din ultimele 7 zile (inclusiv azi). */
    fun doneLastWeek(exercise: Int): Int {
        val from = today.minusDays(6)
        return sessions.count { it.exercise == exercise && it.day()?.let { d -> !d.isBefore(from) } == true }
    }

    fun doneToday(exercise: Int) = sessions.any { it.exercise == exercise && it.day() == today }

    /** Exercițiul propus acum: cel din plan făcut cel mai rar săptămâna asta și nefăcut azi. */
    fun nextExercise(): PlanItem? = patient.plan
        .filter { !doneToday(it.exercise) && doneLastWeek(it.exercise) < it.perWeek }
        .minByOrNull { doneLastWeek(it.exercise) }

    val weeklyTarget get() = patient.plan.sumOf { it.perWeek }
    val weeklyDone get() = patient.plan.sumOf { minOf(doneLastWeek(it.exercise), it.perWeek) }

    /** Câte sesiuni au fost în fiecare din ultimele 7 zile, de la cea mai veche la azi. */
    fun lastSevenDays(): List<Pair<LocalDate, Int>> = (6 downTo 0).map { back ->
        val day = today.minusDays(back.toLong())
        day to sessions.count { it.day() == day }
    }

    /** Zile la rând cu cel puțin o sesiune (azi poate lipsi încă). */
    fun streak(): Int {
        val days = sessions.mapNotNull { it.day() }.toSet()
        var day = if (today in days) today else today.minusDays(1)
        var count = 0
        while (day in days) {
            count++
            day = day.minusDays(1)
        }
        return count
    }

    val tips = listOf(
        "Respiră normal în timpul exercițiului. Nu-ți ține respirația.",
        "Mișcările lente și controlate contează mai mult decât viteza.",
        "Pune telefonul la 2–3 metri, ca să se vadă tot corpul.",
        "Dacă simți o durere ascuțită, oprește-te și scrie-i medicului.",
    )

    fun tipOfTheDay() = tips[today.dayOfYear % tips.size]

    private fun at(daysAgo: Long, hour: Int = 18): String =
        today.minusDays(daysAgo).atTime(LocalTime.of(hour, 0)).toString().let { if (it.length == 16) "$it:00" else it }

    private fun demoSessions(): List<Session> {
        // (zile în urmă, exercițiu, scor, repetări, amplitudine, recenzia medicului)
        val rows = listOf(
            Row(27, 1, 29.5, 8, 118.0, null),
            Row(26, 2, 31.0, 9, 24.0, null),
            Row(24, 5, 26.0, 6, 62.0, "Coboară doar cât te simți confortabil. Adâncimea o creștem treptat."),
            Row(20, 1, 32.0, 9, 126.0, null),
            Row(19, 2, 33.5, 10, 27.0, "Înclinările sunt corecte, dar mai lente ar fi mai bine: 2–3 secunde pe fiecare parte."),
            Row(17, 5, 29.0, 7, 68.0, null),
            Row(13, 1, 35.0, 10, 133.0, "Amplitudine bună. Păstrează trunchiul drept, fără să te lași pe spate."),
            Row(12, 2, 36.0, 10, 29.0, null),
            Row(10, 5, 31.5, 8, 74.0, null),
            Row(6, 1, 38.0, 10, 139.0, null),
            Row(5, 2, 39.5, 10, 31.0, "Foarte bine! Șoldurile au rămas pe loc toată sesiunea."),
            Row(3, 5, 34.0, 8, 79.0, null),
            Row(1, 1, 41.5, 10, 146.0, "Cea mai bună sesiune de până acum. Continuăm la fel."),
        )
        return rows.mapIndexed { i, r ->
            val reps = demoReps(i, r)
            val rom = reps.mapNotNull { it.rom }
            val third = maxOf(1, rom.size / 3)
            Session(
                id = 100_000 + i,
                created = at(r.daysAgo),
                exercise = r.exercise,
                durationS = 55.0 + r.reps * 2.5,
                kept = 0.93 + (i % 5) * 0.01,
                reps = r.reps,
                romMean = rom.average(),
                romFatigue = rom.takeLast(third).average() / rom.take(third).average(),
                score = r.score,
                scoreError = 6.0,
                looksLike = r.exercise,
                warnings = if (i == 2) listOf("Ai ieșit din cadru de câteva ori. Așază telefonul puțin mai departe.") else emptyList(),
                feedback = FEEDBACK.getValue(r.exercise).take(if (r.score >= 38) 1 else 2)
                    .mapIndexed { k, text -> text to (3 - k) }.toMap(),
                reviewText = r.review,
                reviewAuthor = r.review?.let { doctor.name },
                reviewCreated = r.review?.let { at(r.daysAgo - 1, 11) },
                repDetails = reps,
            )
        }
    }

    /**
     * Repetări inventate, dar de mărimea celor reale din KIMORE: la o sesiune mai slabă, spre final
     * amplitudinea scade, ritmul se grăbește, mișcarea devine mai smucită și compensarea crește.
     */
    private fun demoReps(seed: Int, r: Row): List<RepDetail> {
        val random = java.util.Random(seed.toLong())
        fun noise(scale: Double) = (random.nextDouble() * 2 - 1) * scale
        fun round(x: Double) = Math.round(x * 100) / 100.0
        val quality = ((r.score - 26) / 16).coerceIn(0.0, 1.0)
        val tempo = if (r.exercise == 2) 2.1 else 1.3
        val compensation = if (r.exercise == 5) 18.0 else 7.0
        val asymmetry = mapOf(1 to 22.0, 5 to 13.0)[r.exercise]
        return List(r.reps) { k ->
            val late = k.toDouble() / maxOf(1, r.reps - 1) // 0 la prima repetare, 1 la ultima
            val tired = (1 - quality) * late
            RepDetail(
                rom = round(r.rom * (1.04 - 0.14 * tired) + noise(r.rom * 0.03)),
                upS = round((tempo * (1 - 0.2 * tired) + noise(0.12)).coerceAtLeast(0.4)),
                downS = round((tempo * 0.9 * (1 - 0.2 * tired) + noise(0.12)).coerceAtLeast(0.4)),
                jerk = round(Math.pow(10.0, 3.3 - 0.5 * quality + 0.3 * tired + noise(0.08))),
                compensation = round((compensation * (1.3 - 0.5 * quality) * (1 + 0.5 * tired) + noise(1.0)).coerceAtLeast(0.5)),
                asymmetry = asymmetry?.let { round((it * (1.2 - 0.4 * quality) + noise(3.0)).coerceAtLeast(0.5)) },
            )
        }
    }

    private fun demoMessages(): List<Message> {
        val rows = listOf(
            Triple(28L, "doctor", "Bun venit! Planul pentru primele săptămâni: ridicarea brațelor, înclinările laterale și " +
                "genuflexiunile, de 3 ori pe săptămână. Oprește-te dacă apare durere ascuțită."),
            Triple(26L, "patient", "Mulțumesc! La înclinări simt o ușoară tensiune pe partea dreaptă. E normal?"),
            Triple(25L, "doctor", "Da, o tensiune ușoară e normală la început. Nu forța amplitudinea; o creștem treptat."),
            Triple(12L, "patient", "Genuflexiunile îmi par mai ușoare de săptămâna asta."),
            Triple(11L, "doctor", "Se vede și în rezultate. Încearcă să cobori puțin mai mult, dar fără durere."),
            Triple(0L, "doctor", "Am văzut ultima sesiune: ridicarea brațelor arată mult mai bine! " +
                "Joi vorbim la consultația video despre pașii următori."),
        )
        return rows.mapIndexed { i, (days, role, text) ->
            val author = if (role == "doctor") doctor.name else patient.name
            Message(i + 1, at(days, if (role == "doctor") 9 else 20), role, author, text)
        }
    }

    private data class Row(val daysAgo: Long, val exercise: Int, val score: Double, val reps: Int, val rom: Double, val review: String?)

    private companion object {
        // Mesaje reale din config/feedback.json, ca exemplu de observații spuse în timpul exercițiului.
        val FEEDBACK = mapOf(
            1 to listOf("Ține coatele întinse.", "Ridică ambele brațe la fel de sus."),
            2 to listOf("Mișcă-te mai încet, controlat.", "Înclină-te la fel de mult în ambele părți."),
            5 to listOf("Coboară puțin mai mult.", "Ține spatele cât mai drept."),
        )
    }
}

/** Ziua unei sesiuni, sau null dacă data nu se poate citi. */
fun Session.day(): LocalDate? = runCatching { LocalDateTime.parse(created).toLocalDate() }.getOrNull()

/** Cum se face fiecare exercițiu: pași scurți și ce îți trebuie. */
object ExerciseGuide {
    fun steps(exercise: Int): List<String> = when (exercise) {
        1 -> listOf(
            "Stai drept, cu brațele pe lângă corp.",
            "Ridică brațele întinse prin față, până deasupra capului.",
            "Coboară-le încet înapoi.",
        )
        2 -> listOf(
            "Ridică brațele deasupra capului.",
            "Înclină trunchiul încet spre stânga, apoi revino.",
            "Fă la fel spre dreapta. Șoldurile rămân pe loc.",
        )
        3 -> listOf(
            "Ține bastonul în față, la nivelul umerilor.",
            "Rotește trunchiul spre stânga, apoi spre dreapta.",
            "Bazinul și picioarele rămân pe loc.",
        )
        4 -> listOf(
            "Pune mâinile pe șolduri.",
            "Rotește bazinul încet, ca și cum ai desena un cerc.",
            "Umerii rămân nemișcați.",
        )
        else -> listOf(
            "Ține bastonul în față, cu brațele întinse.",
            "Coboară ca și cum te-ai așeza pe un scaun.",
            "Urcă încet înapoi. Spatele rămâne drept.",
        )
    }

    fun equipment(exercise: Int): String? = if (exercise == 3 || exercise == 5) "un baston sau o coadă de mătură" else null

    const val MINUTES = 2
}
