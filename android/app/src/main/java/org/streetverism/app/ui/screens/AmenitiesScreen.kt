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

    // Dynamic distance sorting based on real-time live GPS fix
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
        // Title Header
        Column {
            Text(
                text = "CRISIS AMENITIES & ESSENTIALS",
                fontSize = 18.sp,
                fontWeight = FontWeight.Black,
                color = Color.White,
                letterSpacing = 0.5.sp
            )
            Text(
                text = "Verified offline emergency supplies within walking distance. Sorted by proximity to live GPS.",
                fontSize = 12.sp,
                color = TextSecondary
            )
        }

        // Search Bar (Dark Tactical Slate)
        OutlinedTextField(
            value = searchQuery,
            onValueChange = { searchQuery = it },
            placeholder = { Text("Search insulin, trauma, clean water, blankets...", color = TextMuted, fontSize = 13.sp) },
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

        // Type Filter Chips (Monochrome Slate)
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            item {
                FilterChip(
                    selected = selectedType == null,
                    onClick = { selectedType = null },
                    label = { Text("All Resources (${amenities.size})", fontSize = 11.sp, fontWeight = FontWeight.Bold) },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = ActionSlateActive,
                        selectedLabelColor = Color.White,
                        containerColor = DarkSurface,
                        labelColor = TextSecondary
                    ),
                    shape = RoundedCornerShape(6.dp)
                )
            }
            items(AmenityType.values()) { type ->
                FilterChip(
                    selected = selectedType == type,
                    onClick = { selectedType = type },
                    label = { Text("[${type.code}] ${type.label}", fontSize = 11.sp, fontWeight = FontWeight.Bold) },
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

        // Amenities List (Sorted live by proximity)
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
                        .clip(RoundedCornerShape(8.dp))
                        .background(DarkSurface)
                        .border(1.dp, DarkBorder, RoundedCornerShape(8.dp))
                        .clickable { onNavigateToAmenityOnMap(item) }
                        .padding(14.dp)
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.Top
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Box(
                                        modifier = Modifier
                                            .clip(RoundedCornerShape(3.dp))
                                            .background(ActionSlate)
                                            .padding(horizontal = 5.dp, vertical = 2.dp)
                                    ) {
                                        Text(item.type.code, fontSize = 9.sp, fontWeight = FontWeight.Black, color = Color.White)
                                    }
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
                                    modifier = Modifier.padding(top = 3.dp)
                                )
                            }

                            // Live Distance Badge
                            Column(horizontalAlignment = Alignment.End) {
                                Text(
                                    text = if (distMeters < 1000) "${distMeters.toInt()}m" else "${String.format(java.util.Locale.US, "%.1f", distMeters / 1000)}km",
                                    fontSize = 16.sp,
                                    fontWeight = FontWeight.ExtraBold,
                                    color = SafeGreen
                                )
                                Text(
                                    text = "Head $compass · ~${walkMins}m",
                                    fontSize = 11.sp,
                                    color = TextMuted
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

                        HorizontalDivider(color = DarkBorder, thickness = 1.dp)

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = if (item.is24x7) "24x7 OPEN" else "LIMITED HOURS",
                                fontSize = 10.sp,
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
                                    Text("Dial ${item.contactNumber.take(12)}", fontSize = 11.sp, color = TextPrimary, fontWeight = FontWeight.Bold)
                                }

                                // Route button
                                Button(
                                    onClick = { onNavigateToAmenityOnMap(item) },
                                    colors = ButtonDefaults.buttonColors(containerColor = ActionSlate),
                                    shape = RoundedCornerShape(4.dp),
                                    contentPadding = PaddingValues(horizontal = 10.dp, vertical = 2.dp)
                                ) {
                                    Text("Route Path ➔", fontSize = 11.sp, color = Color.White, fontWeight = FontWeight.Bold)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
