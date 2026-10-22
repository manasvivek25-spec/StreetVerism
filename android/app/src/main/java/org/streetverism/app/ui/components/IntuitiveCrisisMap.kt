package org.streetverism.app.ui.components

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.streetverism.app.model.*
import org.streetverism.app.ui.theme.*
import kotlin.math.*

@Composable
fun IntuitiveCrisisMap(
    userLat: Double,
    userLng: Double,
    hazardZones: List<HazardZone>,
    amenities: List<Amenity>,
    onSelectAmenity: (Amenity) -> Unit
) {
    var selectedFilter by remember { mutableStateOf<AmenityType?>(null) }
    var selectedAmenity by remember { mutableStateOf<Amenity?>(null) }

    // Find nearest safe shelter for primary escape azimuth arrow
    val nearestShelter = remember(userLat, userLng, amenities) {
        amenities.filter { it.type == AmenityType.SHELTER }
            .minByOrNull { it.distanceMetersTo(userLat, userLng) }
    }

    val filteredAmenities = remember(selectedFilter, amenities) {
        if (selectedFilter == null) amenities else amenities.filter { it.type == selectedFilter }
    }

    // Pulsing animation for user dot
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val pulseRadius by infiniteTransition.animateFloat(
        initialValue = 10f,
        targetValue = 28f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "pulseRadius"
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
    ) {
        // --- CALM EMERGENCY HEADER WITH BIG AZIMUTH COMPASS ---
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(DarkSurface)
                .padding(horizontal = 16.dp, vertical = 12.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(text = "🚨", fontSize = 16.sp)
                        Text(
                            text = "OFFICIAL HAZARD ZONE (ADYAR)",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.ExtraBold,
                            color = AlertRed
                        )
                    }

                    Spacer(modifier = Modifier.height(2.dp))

                    if (nearestShelter != null) {
                        val distM = nearestShelter.distanceMetersTo(userLat, userLng)
                        val compass = nearestShelter.compassDirectionFrom(userLat, userLng)
                        val walkMins = max(1, (distM / 75.0).toInt()) // ~4.5 km/h walking speed

                        Text(
                            text = "Escape Compass: Head $compass ➔ ${distM.toInt()}m (${walkMins} min walk)",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = SafeGreen
                        )
                        Text(
                            text = "To: ${nearestShelter.name}",
                            fontSize = 11.sp,
                            color = TextSecondary,
                            maxLines = 1
                        )
                    }
                }

                // Compass Azimuth Indicator Badge
                if (nearestShelter != null) {
                    val compass = nearestShelter.compassDirectionFrom(userLat, userLng)
                    Box(
                        modifier = Modifier
                            .size(54.dp)
                            .clip(CircleShape)
                            .background(DarkSurfaceElevated)
                            .border(2.dp, SafeGreen, CircleShape),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(text = "🧭", fontSize = 14.sp)
                            Text(
                                text = compass,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Black,
                                color = Color.White
                            )
                        }
                    }
                }
            }
        }

        // --- FILTER CHIPS ---
        LazyRow(
            modifier = Modifier
                .fillMaxWidth()
                .background(DarkSurfaceElevated)
                .padding(horizontal = 12.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            item {
                FilterChip(
                    selected = selectedFilter == null,
                    onClick = { selectedFilter = null },
                    label = { Text("All Resources (${amenities.size})") },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = ActionBlue,
                        selectedLabelColor = Color.White
                    )
                )
            }
            items(AmenityType.values()) { type ->
                FilterChip(
                    selected = selectedFilter == type,
                    onClick = { selectedFilter = type },
                    label = { Text("${type.icon} ${type.label}") },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = ActionBlue,
                        selectedLabelColor = Color.White
                    )
                )
            }
        }

        // --- VECTOR MAP CANVAS ---
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .background(DarkBackground)
        ) {
            // Coordinate mapping parameters (centered on user location)
            // Latitude range: ~12.97 to 13.07
            // Longitude range: ~80.20 to 80.28
            val centerLat = 13.015
            val centerLng = 80.225
            val spanLat = 0.08
            val spanLng = 0.08

            Canvas(
                modifier = Modifier
                    .fillMaxSize()
                    .pointerInput(filteredAmenities) {
                        detectTapGestures { tapOffset ->
                            // Hit test for amenity pins
                            val w = size.width
                            val h = size.height

                            for (item in filteredAmenities) {
                                val x = ((item.lng - (centerLng - spanLng / 2)) / spanLng * w).toFloat()
                                val y = (( (centerLat + spanLat / 2) - item.lat) / spanLat * h).toFloat()
                                val dist = hypot(tapOffset.x - x, tapOffset.y - y)
                                if (dist < 40f) {
                                    selectedAmenity = item
                                    onSelectAmenity(item)
                                    break
                                }
                            }
                        }
                    }
            ) {
                val canvasWidth = size.width
                val canvasHeight = size.height

                fun toCanvasX(lng: Double): Float {
                    return ((lng - (centerLng - spanLng / 2)) / spanLng * canvasWidth).toFloat()
                }

                fun toCanvasY(lat: Double): Float {
                    return (((centerLat + spanLat / 2) - lat) / spanLat * canvasHeight).toFloat()
                }

                // 1. Draw subtle background coordinate grid
                val gridColor = Color(0x15FFFFFF)
                for (i in 1..7) {
                    val x = canvasWidth * (i / 8f)
                    val y = canvasHeight * (i / 8f)
                    drawLine(gridColor, Offset(x, 0f), Offset(x, canvasHeight), strokeWidth = 1f)
                    drawLine(gridColor, Offset(0f, y), Offset(canvasWidth, y), strokeWidth = 1f)
                }

                // 2. Draw Vector Hazard Zones
                for (zone in hazardZones) {
                    if (zone.polygon.size >= 3) {
                        val path = Path()
                        val firstPt = zone.polygon.first()
                        path.moveTo(toCanvasX(firstPt.first), toCanvasY(firstPt.second))

                        for (pt in zone.polygon.drop(1)) {
                            path.lineTo(toCanvasX(pt.first), toCanvasY(pt.second))
                        }
                        path.close()

                        val fillColor = when (zone.status) {
                            HazardStatus.OFFICIAL_HAZARD -> Color(0x35EF4444)
                            HazardStatus.LIKELY_HAZARD -> Color(0x30F97316)
                            HazardStatus.UNVERIFIED -> Color(0x25EAB308)
                            HazardStatus.CONTRADICTED -> Color(0x20818CF8)
                            HazardStatus.CLEAR -> Color(0x2510B981)
                        }

                        val strokeColor = when (zone.status) {
                            HazardStatus.OFFICIAL_HAZARD -> AlertRed
                            HazardStatus.LIKELY_HAZARD -> CautionOrange
                            HazardStatus.UNVERIFIED -> WarningYellow
                            HazardStatus.CONTRADICTED -> Color(0xFF818CF8)
                            HazardStatus.CLEAR -> SafeGreen
                        }

                        drawPath(path, fillColor)
                        drawPath(path, strokeColor, style = Stroke(width = 2.5f))
                    }
                }

                // 3. Draw Escape Path Guideline to nearest shelter
                if (nearestShelter != null) {
                    val uX = toCanvasX(userLng)
                    val uY = toCanvasY(userLat)
                    val sX = toCanvasX(nearestShelter.lng)
                    val sY = toCanvasY(nearestShelter.lat)

                    // Dashed guidance line
                    drawLine(
                        color = SafeGreen,
                        start = Offset(uX, uY),
                        end = Offset(sX, sY),
                        strokeWidth = 3f
                    )
                }

                // 4. Draw Amenity Markers
                for (item in filteredAmenities) {
                    val aX = toCanvasX(item.lng)
                    val aY = toCanvasY(item.lat)

                    val isSelected = selectedAmenity?.id == item.id
                    val pinColor = when (item.type) {
                        AmenityType.HOSPITAL -> AlertRed
                        AmenityType.PHARMACY -> SafeGreen
                        AmenityType.FOOD_WATER -> ActionBlue
                        AmenityType.FIRST_AID -> WarningYellow
                        AmenityType.SHELTER -> PurpleReplay
                    }

                    // Marker outer glow if selected
                    if (isSelected) {
                        drawCircle(Color.White, radius = 18f, center = Offset(aX, aY))
                    }

                    // Outer Pin Ring
                    drawCircle(Color(0xFF0F172A), radius = 14f, center = Offset(aX, aY))
                    drawCircle(pinColor, radius = 11f, center = Offset(aX, aY))
                    drawCircle(Color.White, radius = 4f, center = Offset(aX, aY))
                }

                // 5. Draw User Location Dot with Pulsing Ring
                val userX = toCanvasX(userLng)
                val userY = toCanvasY(userLat)

                // Pulse ring
                drawCircle(Color(0x443B82F6), radius = pulseRadius, center = Offset(userX, userY))
                // Dark border
                drawCircle(Color(0xFF0F172A), radius = 10f, center = Offset(userX, userY))
                // Bright Core
                drawCircle(ActionBlue, radius = 7f, center = Offset(userX, userY))
                drawCircle(Color.White, radius = 3f, center = Offset(userX, userY))
            }

            // Legend Overlay (Bottom Left)
            Box(
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .padding(8.dp)
                    .clip(RoundedCornerShape(6.dp))
                    .background(Color(0xD90F172A))
                    .padding(8.dp)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text("📍 Blue: You (GPS)", fontSize = 10.sp, color = TextPrimary)
                    Text("🚨 Red: Flooded Hazard", fontSize = 10.sp, color = AlertRed)
                    Text("🛡️ Purple: Safe Shelters", fontSize = 10.sp, color = PurpleReplay)
                    Text("🏥 Red Pin: Hospitals", fontSize = 10.sp, color = Color.White)
                    Text("🍲 Blue Pin: Clean Water", fontSize = 10.sp, color = Color.White)
                }
            }
        }

        // --- SELECTED AMENITY BOTTOM SHEET ---
        if (selectedAmenity != null) {
            val item = selectedAmenity!!
            val dist = item.distanceMetersTo(userLat, userLng)
            val compass = item.compassDirectionFrom(userLat, userLng)
            val walkTime = max(1, (dist / 75.0).toInt())

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(DarkSurfaceElevated)
                    .border(1.dp, ActionBlue, RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp))
                    .padding(16.dp)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(item.type.icon, fontSize = 20.sp)
                            Text(item.name, fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color.White)
                        }

                        IconButton(onClick = { selectedAmenity = null }, modifier = Modifier.size(24.dp)) {
                            Text("✕", color = TextSecondary, fontSize = 14.sp)
                        }
                    }

                    Text(
                        text = "Compass: Head $compass · ${dist.toInt()}m (~$walkTime min walk)",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold,
                        color = SafeGreen
                    )

                    Text(text = item.address, fontSize = 12.sp, color = TextSecondary)

                    if (item.suppliesAvailable.isNotEmpty()) {
                        Text(
                            text = "Supplies: ${item.suppliesAvailable.joinToString(", ")}",
                            fontSize = 11.sp,
                            color = TextMuted
                        )
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = if (item.is24x7) "✓ Open 24/7" else "Daytime Only",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (item.is24x7) SafeGreen else CautionOrange
                        )

                        Text(
                            text = "Emergency Tel: ${item.contactNumber}",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            color = ActionBlue
                        )
                    }
                }
            }
        }
    }
}
