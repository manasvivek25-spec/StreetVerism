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
        Pair("ta", "Tamil (தமிழ்)"),
        Pair("hi", "Hindi (हिन्दी)"),
        Pair("en", "English"),
        Pair("de", "German (Deutsch)"),
        Pair("fr", "French (Français)"),
        Pair("ja", "Japanese (日本語)"),
        Pair("es", "Spanish (Español)")
    )

    val categories = listOf(
        Pair(null, "All"),
        Pair("sos", "SOS Emergency"),
        Pair("medical", "Medical & Injury"),
        Pair("food_water", "Food & Water"),
        Pair("directions", "Escape & Roads"),
        Pair("authorities", "Civil Defence"),
        Pair("identity", "Embassy & ID"),
        Pair("essentials", "Utilities")
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
                text = "OFFLINE BILINGUAL TRANSLATOR",
                fontSize = 18.sp,
                fontWeight = FontWeight.Black,
                color = Color.White,
                letterSpacing = 0.5.sp
            )
            Text(
                text = "Fixed pre-compiled emergency lexicon. Tap any card for full-screen rescuer view.",
                fontSize = 12.sp,
                color = TextSecondary
            )
        }

        // Language Selector Row (Tactical Slate)
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                text = "TRANSLATE INTO:",
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                color = TextMuted,
                letterSpacing = 1.sp
            )

            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(languages) { (code, label) ->
                    val isSelected = targetLanguage == code
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .background(if (isSelected) ActionSlateActive else DarkSurface)
                            .border(1.dp, if (isSelected) Color.White else DarkBorder, RoundedCornerShape(6.dp))
                            .clickable { targetLanguage = code }
                            .padding(horizontal = 10.dp, vertical = 6.dp)
                    ) {
                        Text(
                            text = label,
                            fontSize = 11.sp,
                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                            color = if (isSelected) Color.White else TextSecondary
                        )
                    }
                }
            }
        }

        // Search Bar
        OutlinedTextField(
            value = searchQuery,
            onValueChange = { searchQuery = it },
            placeholder = { Text("Search English phrase or phonetics...", color = TextMuted, fontSize = 13.sp) },
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

        // Category Filter Chips
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            items(categories) { (catKey, catLabel) ->
                FilterChip(
                    selected = selectedCategory == catKey,
                    onClick = { selectedCategory = catKey },
                    label = { Text(catLabel, fontSize = 11.sp, fontWeight = FontWeight.Bold) },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = ActionSlateActive,
                        selectedLabelColor = Color.White,
                        containerColor = DarkSurface,
                        labelColor = TextSecondary
                    ),
                    shape = RoundedCornerShape(6.dp)
                )
            }
        }

        // Phrases List
        LazyColumn(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            items(filteredPhrases) { phrase ->
                val translation = phrase.resolve(targetLanguage)

                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(DarkSurface)
                        .border(1.dp, DarkBorder, RoundedCornerShape(8.dp))
                        .clickable { fullScreenPhrase = phrase }
                        .padding(14.dp)
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = phrase.category.uppercase(),
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Black,
                                color = TextMuted,
                                letterSpacing = 1.sp
                            )
                            Text(
                                text = "TAP TO EXPAND ➔",
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold,
                                color = SafeGreen
                            )
                        }

                        // Local Script (High contrast)
                        Text(
                            text = translation.text,
                            fontSize = 18.sp,
                            fontWeight = FontWeight.ExtraBold,
                            color = Color.White
                        )

                        // Phonetic pronunciation
                        if (translation.phonetic.isNotBlank() && translation.phonetic != translation.text) {
                            Text(
                                text = "Pronunciation: \"${translation.phonetic}\"",
                                fontSize = 12.sp,
                                color = WarningYellow,
                                fontWeight = FontWeight.Medium
                            )
                        }

                        // English meaning
                        Text(
                            text = phrase.english,
                            fontSize = 13.sp,
                            color = TextSecondary
                        )
                    }
                }
            }
        }
    }

    // Fullscreen Rescuer Flashcard Mode
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
                    .background(Color(0xFF090A0C))
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
                            text = "EMERGENCY BILINGUAL CARD",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Black,
                            color = AlertRed,
                            letterSpacing = 1.sp
                        )

                        Button(
                            onClick = { fullScreenPhrase = null },
                            colors = ButtonDefaults.buttonColors(containerColor = ActionSlate),
                            shape = RoundedCornerShape(4.dp)
                        ) {
                            Text("CLOSE", color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                        }
                    }

                    // Main Display
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(20.dp)
                    ) {
                        Text(
                            text = "SHOW THIS DISPLAY TO FIRST RESPONDERS / LOCALS:",
                            fontSize = 11.sp,
                            color = TextMuted,
                            textAlign = TextAlign.Center,
                            letterSpacing = 1.sp
                        )

                        Text(
                            text = translation.text,
                            fontSize = 32.sp,
                            fontWeight = FontWeight.Black,
                            color = Color.White,
                            textAlign = TextAlign.Center,
                            lineHeight = 44.sp
                        )

                        if (translation.phonetic.isNotBlank() && translation.phonetic != translation.text) {
                            Text(
                                text = "Phonetic: \"${translation.phonetic}\"",
                                fontSize = 17.sp,
                                fontWeight = FontWeight.Bold,
                                color = WarningYellow,
                                textAlign = TextAlign.Center
                            )
                        }

                        HorizontalDivider(color = DarkBorder, thickness = 1.dp, modifier = Modifier.padding(vertical = 8.dp))

                        Text(
                            text = "English: ${phrase.english}",
                            fontSize = 15.sp,
                            color = TextSecondary,
                            textAlign = TextAlign.Center
                        )
                    }

                    Text(
                        text = "100% Offline · Zero Network Required",
                        fontSize = 11.sp,
                        color = TextMuted
                    )
                }
            }
        }
    }
}
