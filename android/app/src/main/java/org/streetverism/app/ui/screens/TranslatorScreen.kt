package org.streetverism.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import org.streetverism.app.model.TranslationPhrase
import org.streetverism.app.ui.theme.*

@Composable
fun TranslatorScreen(
    userLanguage: String,
    phrases: List<TranslationPhrase>
) {
    var targetLanguage by remember { mutableStateOf(if (userLanguage == "ta") "en" else "ta") }
    var searchQuery by remember { mutableStateOf("") }
    var selectedCategory by remember { mutableStateOf<String?>(null) }
    var fullScreenPhrase by remember { mutableStateOf<TranslationPhrase?>(null) }

    val languages = listOf(
        Pair("ta", "🇮🇳 தமிழ் (Tamil)"),
        Pair("hi", "🇮🇳 हिन्दी (Hindi)"),
        Pair("en", "🇬🇧 English"),
        Pair("de", "🇩🇪 Deutsch"),
        Pair("fr", "🇫🇷 Français"),
        Pair("ja", "🇯🇵 日本語"),
        Pair("es", "🇪🇸 Español")
    )

    val categories = listOf(
        Pair(null, "All Phrases"),
        Pair("sos", "🚨 Life SOS"),
        Pair("medical", "🏥 Medical"),
        Pair("food_water", "🍲 Water & Food"),
        Pair("directions", "🧭 Roads & Escape"),
        Pair("authorities", "🛡️ Civil Defence"),
        Pair("identity", "🛂 Embassy & ID"),
        Pair("essentials", "⚡ Essentials")
    )

    val filteredPhrases = remember(searchQuery, selectedCategory, targetLanguage, phrases) {
        phrases.filter { phrase ->
            val matchesCategory = selectedCategory == null || phrase.category == selectedCategory
            val matchesSearch = searchQuery.isBlank() ||
                    phrase.english.contains(searchQuery, ignoreCase = true) ||
                    phrase.resolve(targetLanguage).text.contains(searchQuery, ignoreCase = true) ||
                    phrase.resolve(targetLanguage).phonetic.contains(searchQuery, ignoreCase = true)
            matchesCategory && matchesSearch
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // Header
        Column {
            Text(
                text = "Offline Crisis Translator",
                fontSize = 20.sp,
                fontWeight = FontWeight.ExtraBold,
                color = Color.White
            )
            Text(
                text = "100% offline fixed dictionary. Tap any phrase to display full-screen to a local.",
                fontSize = 12.sp,
                color = TextSecondary
            )
        }

        // Target Language Selector Bar
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            items(languages) { (code, label) ->
                FilterChip(
                    selected = targetLanguage == code,
                    onClick = { targetLanguage = code },
                    label = { Text(label, fontSize = 12.sp) },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = ActionBlue,
                        selectedLabelColor = Color.White
                    )
                )
            }
        }

        // Search Bar
        OutlinedTextField(
            value = searchQuery,
            onValueChange = { searchQuery = it },
            placeholder = { Text("Search symptom, need water, trapped, road...", color = TextMuted) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            colors = OutlinedTextFieldDefaults.colors(
                focusedTextColor = Color.White,
                unfocusedTextColor = Color.White,
                focusedBorderColor = ActionBlue,
                unfocusedBorderColor = DarkBorder,
                focusedContainerColor = DarkSurface,
                unfocusedContainerColor = DarkSurface
            )
        )

        // Category Pills
        LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            items(categories) { (catId, catLabel) ->
                val isSelected = selectedCategory == catId
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(16.dp))
                        .background(if (isSelected) ActionBlue else DarkSurfaceElevated)
                        .clickable { selectedCategory = catId }
                        .padding(horizontal = 12.dp, vertical = 6.dp)
                ) {
                    Text(
                        text = catLabel,
                        fontSize = 12.sp,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                        color = if (isSelected) Color.White else TextSecondary
                    )
                }
            }
        }

        // Phrase List
        LazyColumn(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            items(filteredPhrases) { phrase ->
                val translation = phrase.resolve(targetLanguage)

                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .background(DarkSurface)
                        .border(1.dp, DarkBorder, RoundedCornerShape(12.dp))
                        .clickable { fullScreenPhrase = phrase }
                        .padding(14.dp)
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        // English Original
                        Text(
                            text = phrase.english,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = Color.White
                        )

                        // Target Native Translation
                        Text(
                            text = translation.text,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold,
                            color = ActionBlue
                        )

                        // Phonetic pronunciation guide
                        if (translation.phonetic.isNotBlank() && translation.phonetic != translation.text) {
                            Text(
                                text = "🗣️ Pronounce: \"${translation.phonetic}\"",
                                fontSize = 12.sp,
                                color = WarningYellow
                            )
                        }

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.End
                        ) {
                            Text(
                                text = "Tap for Fullscreen Emergency Card ➔",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = TextMuted
                            )
                        }
                    }
                }
            }
        }
    }

    // --- FULLSCREEN EMERGENCY FLASHCARD MODAL ---
    if (fullScreenPhrase != null) {
        val phrase = fullScreenPhrase!!
        val translation = phrase.resolve(targetLanguage)

        Dialog(
            onDismissRequest = { fullScreenPhrase = null },
            properties = DialogProperties(usePlatformDefaultWidth = false)
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color.Black)
                    .padding(24.dp)
            ) {
                Column(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.SpaceBetween,
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    // Top Bar
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "EMERGENCY PHRASE CARD",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            color = AlertRed
                        )

                        Button(
                            onClick = { fullScreenPhrase = null },
                            colors = ButtonDefaults.buttonColors(containerColor = DarkSurfaceElevated)
                        ) {
                            Text("✕ Close", color = Color.White)
                        }
                    }

                    // Main Giant Display (Show to local first responder)
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(20.dp)
                    ) {
                        Text(
                            text = "SHOW THIS SCREEN TO RESCUER / CITIZEN:",
                            fontSize = 11.sp,
                            color = TextMuted,
                            textAlign = TextAlign.Center
                        )

                        Text(
                            text = translation.text,
                            fontSize = 32.sp,
                            fontWeight = FontWeight.Black,
                            color = Color.White,
                            textAlign = TextAlign.Center,
                            lineHeight = 42.sp
                        )

                        if (translation.phonetic.isNotBlank() && translation.phonetic != translation.text) {
                            Text(
                                text = "🗣️ Phonetic: \"${translation.phonetic}\"",
                                fontSize = 18.sp,
                                fontWeight = FontWeight.Bold,
                                color = WarningYellow,
                                textAlign = TextAlign.Center
                            )
                        }

                        Divider(color = DarkBorder, thickness = 1.dp, modifier = Modifier.padding(vertical = 8.dp))

                        Text(
                            text = "English: ${phrase.english}",
                            fontSize = 15.sp,
                            color = TextSecondary,
                            textAlign = TextAlign.Center
                        )
                    }

                    // Bottom instruction
                    Text(
                        text = "High Contrast Mode · 100% Offline · No Data Required",
                        fontSize = 12.sp,
                        color = SafeGreen
                    )
                }
            }
        }
    }
}
