package org.streetverism.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.streetverism.app.model.UserProfile
import org.streetverism.app.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(
    currentProfile: UserProfile?,
    onSaveProfile: (UserProfile) -> Unit
) {
    var name by remember { mutableStateOf(currentProfile?.name ?: "") }
    var ageText by remember { mutableStateOf(currentProfile?.age?.toString() ?: "") }
    var selectedLanguage by remember { mutableStateOf(currentProfile?.language ?: "en") }
    var nationality by remember { mutableStateOf(currentProfile?.nationality ?: "") }
    var expandedLangDropdown by remember { mutableStateOf(false) }

    val ageInt = ageText.toIntOrNull() ?: 25
    val previewProfile = UserProfile(
        name = name,
        age = ageInt,
        language = selectedLanguage,
        nationality = nationality
    )

    val supportedLanguages = listOf(
        Pair("en", "English"),
        Pair("ta", "Tamil (தமிழ்)"),
        Pair("hi", "Hindi (हिन्दी)"),
        Pair("de", "German (Deutsch)"),
        Pair("fr", "French (Français)"),
        Pair("ja", "Japanese (日本語)"),
        Pair("es", "Spanish (Español)")
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
            .padding(16.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // Header
        Column {
            Text(
                text = "EMERGENCY USER PROFILE",
                fontSize = 18.sp,
                fontWeight = FontWeight.Black,
                color = Color.White,
                letterSpacing = 0.5.sp
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "Only 4 essential fields required for triage and credibility calibration. Stored 100% locally.",
                fontSize = 12.sp,
                color = TextSecondary,
                lineHeight = 16.sp
            )
        }

        // Field 1: Name
        OutlinedTextField(
            value = name,
            onValueChange = { name = it },
            label = { Text("Full Name", color = TextSecondary) },
            placeholder = { Text("e.g. Alex Mercer", color = TextMuted) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            colors = OutlinedTextFieldDefaults.colors(
                focusedTextColor = Color.White,
                unfocusedTextColor = Color.White,
                focusedBorderColor = ActionSlateActive,
                unfocusedBorderColor = DarkBorder,
                focusedContainerColor = DarkSurface,
                unfocusedContainerColor = DarkSurface
            ),
            shape = RoundedCornerShape(6.dp)
        )

        // Field 2: Age
        Column {
            OutlinedTextField(
                value = ageText,
                onValueChange = { input ->
                    if (input.all { it.isDigit() } && input.length <= 3) {
                        ageText = input
                    }
                },
                label = { Text("Age (Years)", color = TextSecondary) },
                placeholder = { Text("e.g. 28", color = TextMuted) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth(),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedTextColor = Color.White,
                    unfocusedTextColor = Color.White,
                    focusedBorderColor = ActionSlateActive,
                    unfocusedBorderColor = DarkBorder,
                    focusedContainerColor = DarkSurface,
                    unfocusedContainerColor = DarkSurface
                ),
                shape = RoundedCornerShape(6.dp)
            )

            Spacer(modifier = Modifier.height(6.dp))

            // Honest Age-Credibility & Vulnerability Card
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(6.dp))
                    .background(DarkSurfaceElevated)
                    .border(1.dp, DarkBorder, RoundedCornerShape(6.dp))
                    .padding(12.dp)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            text = "AGE TRIAGE METRIC",
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Black,
                            color = TextSecondary,
                            letterSpacing = 1.sp
                        )
                        Text(
                            text = previewProfile.vulnerabilityTier(),
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (previewProfile.isVulnerable()) AlertRed else SafeGreen
                        )
                    }

                    Text(
                        text = "• Credibility Multiplier: ${String.format(java.util.Locale.US, "%.2f", previewProfile.calculateCredibilityFactor())}x\n" +
                               "• Triage Role: Calibrates report credibility in Bayesian fusion and flags children (<14) and seniors (>65) for prioritized evacuation.",
                        fontSize = 11.sp,
                        color = TextSecondary,
                        lineHeight = 15.sp
                    )
                }
            }
        }

        // Field 3: Language
        Column {
            Text(
                text = "Primary Crisis Language",
                fontSize = 13.sp,
                fontWeight = FontWeight.SemiBold,
                color = Color.White
            )
            Spacer(modifier = Modifier.height(6.dp))

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(6.dp))
                    .background(DarkSurface)
                    .border(1.dp, DarkBorder, RoundedCornerShape(6.dp))
                    .clickable { expandedLangDropdown = true }
                    .padding(14.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    val currentLabel = supportedLanguages.firstOrNull { it.first == selectedLanguage }?.second ?: "English"
                    Text(text = currentLabel, color = Color.White, fontWeight = FontWeight.Bold)
                    Text(text = "▼", color = TextSecondary, fontSize = 11.sp)
                }

                DropdownMenu(
                    expanded = expandedLangDropdown,
                    onDismissRequest = { expandedLangDropdown = false },
                    modifier = Modifier.background(DarkSurfaceElevated)
                ) {
                    supportedLanguages.forEach { (code, label) ->
                        DropdownMenuItem(
                            text = { Text(text = label, color = Color.White, fontSize = 13.sp) },
                            onClick = {
                                selectedLanguage = code
                                expandedLangDropdown = false
                            }
                        )
                    }
                }
            }
        }

        // Field 4: Nationality
        OutlinedTextField(
            value = nationality,
            onValueChange = { nationality = it },
            label = { Text("Nationality / Home Country", color = TextSecondary) },
            placeholder = { Text("e.g. United Kingdom, Germany, Japan", color = TextMuted) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            colors = OutlinedTextFieldDefaults.colors(
                focusedTextColor = Color.White,
                unfocusedTextColor = Color.White,
                focusedBorderColor = ActionSlateActive,
                unfocusedBorderColor = DarkBorder,
                focusedContainerColor = DarkSurface,
                unfocusedContainerColor = DarkSurface
            ),
            shape = RoundedCornerShape(6.dp)
        )

        Spacer(modifier = Modifier.height(8.dp))

        // Save Button (Tactical Charcoal/Slate)
        Button(
            onClick = {
                val finalName = if (name.isBlank()) "Tourist" else name.trim()
                val finalNationality = if (nationality.isBlank()) "International" else nationality.trim()
                onSaveProfile(
                    UserProfile(
                        name = finalName,
                        age = ageInt,
                        language = selectedLanguage,
                        nationality = finalNationality
                    )
                )
            },
            modifier = Modifier
                .fillMaxWidth()
                .height(48.dp),
            colors = ButtonDefaults.buttonColors(containerColor = ActionSlate),
            shape = RoundedCornerShape(6.dp)
        ) {
            Text(
                text = "SAVE PROFILE & ENTER CRISIS MODE",
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White,
                letterSpacing = 0.5.sp
            )
        }
    }
}
