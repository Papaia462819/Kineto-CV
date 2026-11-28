package ro.kinetocv.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/*
 * Sistemul vizual al aplicației. Principii, pentru că aplicația e folosită și de vârstnici:
 * - text mare (cel mai mic text e 14 sp, textul obișnuit 17 sp), contrast ridicat;
 * - butoane de cel puțin 56 dp înălțime;
 * - starea nu se arată doar prin culoare: are mereu și text sau iconiță.
 */

private val LightColors = lightColorScheme(
    primary = Color(0xFF006A60),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFB2EFE3),
    onPrimaryContainer = Color(0xFF00201C),
    secondary = Color(0xFF4A635F),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFCCE8E2),
    onSecondaryContainer = Color(0xFF05201C),
    tertiary = Color(0xFF9A4A00),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFFFDCC4),
    onTertiaryContainer = Color(0xFF311300),
    error = Color(0xFFB3261E),
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002),
    background = Color(0xFFF3F7F6),
    onBackground = Color(0xFF161D1C),
    surface = Color(0xFFF3F7F6),
    onSurface = Color(0xFF161D1C),
    surfaceVariant = Color(0xFFDAE5E2),
    onSurfaceVariant = Color(0xFF3B4947),
    outline = Color(0xFF6B7A77),
    outlineVariant = Color(0xFFD3DEDB),
    surfaceContainerLowest = Color.White,
    surfaceContainerLow = Color(0xFFEDF3F1),
    surfaceContainer = Color(0xFFE7EEEC),
    surfaceContainerHigh = Color(0xFFE1E9E7),
    surfaceContainerHighest = Color(0xFFDBE4E1),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF84D6C8),
    onPrimary = Color(0xFF003731),
    primaryContainer = Color(0xFF005048),
    onPrimaryContainer = Color(0xFFA0F2E4),
    secondary = Color(0xFFB1CCC6),
    onSecondary = Color(0xFF1C3531),
    secondaryContainer = Color(0xFF334B47),
    onSecondaryContainer = Color(0xFFCCE8E2),
    tertiary = Color(0xFFFFB781),
    onTertiary = Color(0xFF512400),
    tertiaryContainer = Color(0xFF743500),
    onTertiaryContainer = Color(0xFFFFDCC4),
    error = Color(0xFFFFB4AB),
    errorContainer = Color(0xFF93000A),
    onErrorContainer = Color(0xFFFFDAD6),
    background = Color(0xFF0E1514),
    onBackground = Color(0xFFDDE4E2),
    surface = Color(0xFF0E1514),
    onSurface = Color(0xFFDDE4E2),
    surfaceVariant = Color(0xFF3F4947),
    onSurfaceVariant = Color(0xFFBFC9C6),
    outline = Color(0xFF899390),
    outlineVariant = Color(0xFF2E3735),
    surfaceContainerLowest = Color(0xFF151C1B),
    surfaceContainerLow = Color(0xFF1A2120),
    surfaceContainer = Color(0xFF1E2524),
    surfaceContainerHigh = Color(0xFF29302E),
    surfaceContainerHighest = Color(0xFF333B39),
)

/** Culorile de stare (bine / acceptabil / de lucrat), care nu există în paleta Material. */
@Immutable
data class StatusColors(
    val good: Color, val goodContainer: Color, val onGoodContainer: Color,
    val medium: Color, val mediumContainer: Color, val onMediumContainer: Color,
    val weak: Color, val weakContainer: Color, val onWeakContainer: Color,
)

private val LightStatus = StatusColors(
    good = Color(0xFF1E7B3C), goodContainer = Color(0xFFC6EFCF), onGoodContainer = Color(0xFF00210B),
    medium = Color(0xFF8A5F00), mediumContainer = Color(0xFFFFE3A3), onMediumContainer = Color(0xFF2B1D00),
    weak = Color(0xFFB3261E), weakContainer = Color(0xFFFFDAD6), onWeakContainer = Color(0xFF410002),
)

private val DarkStatus = StatusColors(
    good = Color(0xFF8BD89D), goodContainer = Color(0xFF115227), onGoodContainer = Color(0xFFC6EFCF),
    medium = Color(0xFFF2C14E), mediumContainer = Color(0xFF5C4300), onMediumContainer = Color(0xFFFFE3A3),
    weak = Color(0xFFFFB4AB), weakContainer = Color(0xFF8C1D18), onWeakContainer = Color(0xFFFFDAD6),
)

val LocalStatusColors = staticCompositionLocalOf { LightStatus }

private val AppTypography = Typography(
    displayMedium = TextStyle(fontSize = 44.sp, lineHeight = 52.sp, fontWeight = FontWeight.Bold),
    displaySmall = TextStyle(fontSize = 36.sp, lineHeight = 44.sp, fontWeight = FontWeight.Bold),
    headlineLarge = TextStyle(fontSize = 32.sp, lineHeight = 40.sp, fontWeight = FontWeight.Bold),
    headlineMedium = TextStyle(fontSize = 28.sp, lineHeight = 36.sp, fontWeight = FontWeight.Bold),
    headlineSmall = TextStyle(fontSize = 24.sp, lineHeight = 32.sp, fontWeight = FontWeight.SemiBold),
    titleLarge = TextStyle(fontSize = 22.sp, lineHeight = 28.sp, fontWeight = FontWeight.SemiBold),
    titleMedium = TextStyle(fontSize = 19.sp, lineHeight = 26.sp, fontWeight = FontWeight.SemiBold),
    titleSmall = TextStyle(fontSize = 17.sp, lineHeight = 24.sp, fontWeight = FontWeight.Medium),
    bodyLarge = TextStyle(fontSize = 18.sp, lineHeight = 26.sp),
    bodyMedium = TextStyle(fontSize = 17.sp, lineHeight = 24.sp),
    bodySmall = TextStyle(fontSize = 15.sp, lineHeight = 22.sp),
    labelLarge = TextStyle(fontSize = 17.sp, lineHeight = 22.sp, fontWeight = FontWeight.SemiBold),
    labelMedium = TextStyle(fontSize = 15.sp, lineHeight = 20.sp, fontWeight = FontWeight.Medium),
    labelSmall = TextStyle(fontSize = 14.sp, lineHeight = 18.sp, fontWeight = FontWeight.Medium),
)

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(18.dp),
    large = RoundedCornerShape(24.dp),
    extraLarge = RoundedCornerShape(32.dp),
)

/** Mărimea textului aleasă în Profil. Se aplică peste setarea telefonului, nu în locul ei. */
enum class TextSize(val label: String, val factor: Float) {
    Normal("Normal", 1.0f),
    Large("Mare", 1.15f),
    Huge("Foarte mare", 1.3f),
}

@Composable
fun KinetoTheme(
    textSize: TextSize = TextSize.Normal,
    dark: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val density = LocalDensity.current
    CompositionLocalProvider(
        LocalStatusColors provides if (dark) DarkStatus else LightStatus,
        LocalDensity provides Density(density.density, density.fontScale * textSize.factor),
    ) {
        MaterialTheme(
            colorScheme = if (dark) DarkColors else LightColors,
            typography = AppTypography,
            shapes = AppShapes,
            content = content,
        )
    }
}

/** Distanțele folosite peste tot, ca paginile să arate la fel. */
object Space {
    val screen = 20.dp // marginea paginii
    val gap = 16.dp // între carduri
    val inner = 20.dp // în interiorul unui card
    val small = 8.dp
}
