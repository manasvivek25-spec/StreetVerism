package org.streetverism.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val CrisisDarkColorScheme = darkColorScheme(
    primary = ActionBlue,
    onPrimary = Color.White,
    secondary = SafeGreen,
    onSecondary = Color.White,
    tertiary = WarningYellow,
    background = DarkBackground,
    onBackground = TextPrimary,
    surface = DarkSurface,
    onSurface = TextPrimary,
    surfaceVariant = DarkSurfaceElevated,
    onSurfaceVariant = TextSecondary,
    error = AlertRed,
    onError = Color.White
)

@Composable
fun StreetVerismTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = CrisisDarkColorScheme,
        content = content
    )
}
