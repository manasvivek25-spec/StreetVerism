package org.streetverism.app.ui.screens

import android.content.Intent
import android.net.Uri
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.streetverism.app.model.Amenity
import org.streetverism.app.model.AmenityType
import org.streetverism.app.ui.theme.*
import kotlin.math.max

@Composable
fun AmenitiesScreen(
    userLat: Double,
    userLng: Double,
    amenities: List<Amenity>,
    onNavigateToAmenityOnMap: (Amenity) -> Unit
) {
    val context = LocalContext.current
    var selectedType by remember { mutableStateOf<AmenityType?>(null) }
    var searchQuery by remember { mutableStateOf("") }

    // Sorted by distance to current user coordinates
    val sortedAndFiltered = remember(selectedType, searchQuery, userLat, userLng, amenities) {
        amenities
            .filter { item ->
                val matchesType = selectedType == null || item.type == selectedType
                val matchesSearch = searchQuery.isBlank() ||
                        item.name.contains(searchQuery, ignoreCase = true) ||
                        item.address.contains(searchQuery, ignoreCase = true) ||
                        item.suppliesAvailable.any { it.contains(searchQuery, ignoreCase = true) }
                matchesType && matchesSearch
            }
            .sortedBy { it.distanceMetersTo(userLat, userLng) }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // Title
        Column {
            Text(
                text = "Emergency Resource Locator",
                fontSize = 20.sp,
                fontWeight = FontWeight.ExtraBold,
                color = Color.White
            )
            Text(
                text = "Verified offline registry: Food, clean water, pharmacies, hospitals, and shelters.",
                fontSize = 12.sp,
                color = TextSecondary
            )
        }

        // Search Bar
        OutlinedTextField(
            value = searchQuery,
            onValueChange = { searchQuery = it },
            placeholder = { Text("Search insulin, trauma, water, oxygen...", color = TextMuted) },
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

        // Type Filter Chips
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            item {
                FilterChip(
                    selected = selectedType == null,
                    onClick = { selectedType = null },
                    label = { Text("All (${amenities.size})") },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = ActionBlue,
                        selectedLabelColor = Color.White
                    )
                )
            }
            items(AmenityType.values()) { type ->
                FilterChip(
                    selected = selectedType == type,
                    onClick = { selectedType = type },
                    label = { Text("${type.icon} ${type.label}") },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = ActionBlue,
                        selectedLabelColor = Color.White
                    )
                )
            }
        }

        // Amenities List
        LazyColumn(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            items(sortedAndFiltered) { item ->
                val distMeters = item.distanceMetersTo(userLat, userLng)
                val compass = item.compassDirectionFrom(userLat, userLng)
                val walkMins = max(1, (distMeters / 75.0).toInt())

                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .background(DarkSurface)
                        .border(1.dp, DarkBorder, RoundedCornerShape(12.dp))
                        .padding(14.dp)
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.Top
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Text(item.type.icon, fontSize = 18.sp)
                                    Text(
                                        text = item.name,
                                        fontSize = 15.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = Color.White
                                    )
                                }
                                Text(
                                    text = item.address,
                                    fontSize = 12.sp,
                                    color = TextSecondary,
                                    modifier = Modifier.padding(top = 2.dp)
                                )
                            }

                            // Distance Badge
                            Column(horizontalAlignment = Alignment.End) {
                                Text(
                                    text = if (distMeters < 1000) "${distMeters.toInt()}m" else "${String.format("%.1f", distMeters / 1000)}km",
                                    fontSize = 15.sp,
                                    fontWeight = FontWeight.ExtraBold,
                                    color = SafeGreen
                                )
                                Text(
                                    text = "Head $compass (~${walkMins}m)",
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = ActionBlue
                                )
                            }
                        }

                        // Supplies available badges
                        if (item.suppliesAvailable.isNotEmpty()) {
                            Text(
                                text = "Supplies: ${item.suppliesAvailable.joinToString(" · ")}",
                                fontSize = 11.sp,
                                color = TextMuted,
                                lineHeight = 14.sp
                            )
                        }

                        Divider(color = DarkBorder, thickness = 1.dp, modifier = Modifier.padding(vertical = 2.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = if (item.is24x7) "● 24x7 OPEN" else "● LIMITED HOURS",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = if (item.is24x7) SafeGreen else CautionOrange
                            )

                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                // Call facility button
                                TextButton(
                                    onClick = {
                                        val intent = Intent(Intent.ACTION_DIAL).apply {
                                            data = Uri.parse("tel:${item.contactNumber.filter { it.isDigit() || it == '+' }}")
                                        }
                                        context.startActivity(intent)
                                    },
                                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 2.dp)
                                ) {
                                    Text("📞 Call", fontSize = 12.sp, color = ActionBlue, fontWeight = FontWeight.Bold)
                                }

                                // Show on crisis map button
                                Button(
                                    onClick = { onNavigateToAmenityOnMap(item) },
                                    colors = ButtonDefaults.buttonColors(containerColor = ActionBlue),
                                    shape = RoundedCornerShape(6.dp),
                                    contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp)
                                ) {
                                    Text("Compass 🧭", fontSize = 12.sp, color = Color.White, fontWeight = FontWeight.Bold)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
