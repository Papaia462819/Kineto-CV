package ro.kinetocv.app.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.ui.graphics.Color
import ro.kinetocv.app.ui.theme.LocalStatusColors
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import java.util.Locale

private val romanian: Locale = Locale.forLanguageTag("ro")

private fun String.capitalized() = replaceFirstChar { it.titlecase(romanian) }

private fun parse(iso: String): LocalDateTime? = runCatching { LocalDateTime.parse(iso) }.getOrNull()

/** "Azi", "Ieri", "Acum 3 zile", altfel "18 noiembrie". */
fun relativeDay(iso: String): String {
    val date = parse(iso)?.toLocalDate() ?: return iso
    return when (val days = ChronoUnit.DAYS.between(date, LocalDate.now())) {
        0L -> "Azi"
        1L -> "Ieri"
        in 2..6 -> "Acum $days zile"
        else -> date.format(DateTimeFormatter.ofPattern("d MMMM", romanian))
    }
}

/** "Azi, 18:00" sau "18 noiembrie, 18:00". */
fun relativeDayTime(iso: String): String {
    val time = parse(iso) ?: return iso
    return relativeDay(iso) + ", " + time.format(DateTimeFormatter.ofPattern("HH:mm"))
}

/** "Luni, 23 noiembrie" */
fun longDate(date: LocalDate): String = date.format(DateTimeFormatter.ofPattern("EEEE, d MMMM", romanian)).capitalized()

/** "Joi, 26 nov. · 10:00" */
fun appointmentDate(time: LocalDateTime): String =
    time.format(DateTimeFormatter.ofPattern("EEEE, d MMMM · HH:mm", romanian)).capitalized()

/** Prima literă a zilei săptămânii: L, M, M, J, V, S, D. */
fun dayLetter(date: LocalDate): String = date.format(DateTimeFormatter.ofPattern("EEEEE", romanian)).uppercase(romanian)

fun dayName(date: LocalDate): String = date.format(DateTimeFormatter.ofPattern("EEEE", romanian))

fun timeOfDayGreeting(): String = when (LocalDateTime.now().hour) {
    in 5..11 -> "Bună dimineața"
    in 12..17 -> "Bună ziua"
    else -> "Bună seara"
}

/** Nivelul unui scor (0–50), cu pragurile din KIMORE: 40 bine, 30 acceptabil. */
enum class Level(val label: String) {
    Good("Bine"),
    Medium("Acceptabil"),
    Weak("De îmbunătățit"),
    Unknown("Fără scor"),
}

// Pe scorul rotunjit, cum îl vede pacientul: 39,5 apare „40”, deci trebuie să fie și „Bine”.
fun levelOf(score: Double?) = when {
    score == null -> Level.Unknown
    Math.round(score) >= 40 -> Level.Good
    Math.round(score) >= 30 -> Level.Medium
    else -> Level.Weak
}

/** Culoarea principală, fundalul și textul pe fundal pentru un nivel. */
data class LevelColors(val main: Color, val container: Color, val onContainer: Color)

@Composable
@ReadOnlyComposable
fun levelColors(level: Level): LevelColors {
    val s = LocalStatusColors.current
    return when (level) {
        Level.Good -> LevelColors(s.good, s.goodContainer, s.onGoodContainer)
        Level.Medium -> LevelColors(s.medium, s.mediumContainer, s.onMediumContainer)
        Level.Weak -> LevelColors(s.weak, s.weakContainer, s.onWeakContainer)
        Level.Unknown -> LevelColors(Color.Gray, Color.Gray.copy(alpha = 0.2f), Color.DarkGray)
    }
}

fun formatScore(score: Double?) = score?.let { "%.0f".format(it) } ?: "–"
