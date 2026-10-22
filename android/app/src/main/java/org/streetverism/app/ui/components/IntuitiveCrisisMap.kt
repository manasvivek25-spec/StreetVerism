package org.streetverism.app.ui.components

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGestures
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
import java.util.Locale
import kotlin.math.*

@Composable
fun IntuitiveCrisisMap(
    userLat: Double,
    userLng: Double,
    gpsAccuracy: Float = 0f,
    gpsBearing: Float = 0f,
    gpsSpeed: Float = 0f,
    isGpsLive: Boolean = false,
    gpsStatusMessage: String = "GPS Ready",
    hazardZones: List<HazardZone>,
    amenities: List<Amenity>,
    onSelectAmenity: (Amenity) -> Unit
) {
    var selectedFilter by remember { mutableStateOf<AmenityType?>(null) }
    var selectedAmenity by remember { mutableStateOf<Amenity?>(null) }

    // Map viewport state: center coordinates and zoom level
    var mapCenterLat by remember { mutableDoubleStateOf(userLat) }
    var mapCenterLng by remember { mutableDoubleStateOf(userLng) }
    var zoomSpan by remember { mutableDoubleStateOf(0.025) } // ~2.5km street/neighborhood span
    var isFollowingGps by remember { mutableStateOf(true) }

    // Keep map centered on user's live GPS coordinates when in follow mode
    LaunchedEffect(userLat, userLng, isFollowingGps) {
        if (isFollowingGps) {
            mapCenterLat = userLat
            mapCenterLng = userLng
        }
    }

    // Find nearest safe shelter dynamically relative to real-time location
    val nearestShelter = remember(userLat, userLng, amenities) {
        amenities.filter { it.type == AmenityType.SHELTER }
            .minByOrNull { it.distanceMetersTo(userLat, userLng) }
    }

    val filteredAmenities = remember(selectedFilter, amenities) {
        if (selectedFilter == null) amenities else amenities.filter { it.type == selectedFilter }
    }

    // Pulsing radar animation for user's live GPS fix
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
        // --- CALM EMERGENCY HEADER WITH REAL-TIME AZIMUTH COMPASS ---
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(DarkSurface)
                .padding(horizontal = 16.dp, vertical = 10.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(text = if (isGpsLive) "🛰️" else "📍", fontSize = 15.sp)
                        Text(
                            text = if (isGpsLive) "LIVE GPS EMERGENCY RADAR" else "CRISIS HAZARD MAP",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.ExtraBold,
                            color = if (isGpsLive) SafeGreen else AlertRed
                        )
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(if (isGpsLive) Color(0x3510B981) else Color(0x35EF4444))
                                .padding(horizontal = 4.dp, vertical = 1.dp)
                        ) {
                            Text(
                                text = if (isGpsLive) "REAL-TIME" else "STANDBY",
                                fontSize = 8.sp,
                                fontWeight = FontWeight.Black,
                                color = if (isGpsLive) SafeGreen else AlertRed
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(2.dp))

                    if (nearestShelter != null) {
                        val distM = nearestShelter.distanceMetersTo(userLat, userLng)
                        val compass = nearestShelter.compassDirectionFrom(userLat, userLng)
                        val walkMins = max(1, (distM / 75.0).toInt()) // ~4.5 km/h average evacuation walking speed

                        Text(
                            text = "Escape Azimuth: Head $compass ➔ ${distM.toInt()}m (~${walkMins} min)",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = SafeGreen
                        )
                        Text(
                            text = "To: ${nearestShelter.name}",
                            fontSize = 11.sp,
                            color = TextSecondary,
                            maxLines = 1
                        )
                    } else {
                        Text(
                            text = "Searching safe shelter in sector...",
                            fontSize = 12.sp,
                            color = TextSecondary
                        )
                    }
                }

                // Compass Azimuth Indicator Badge
                if (nearestShelter != null) {
                    val compass = nearestShelter.compassDirectionFrom(userLat, userLng)
                    Box(
                        modifier = Modifier
                            .size(52.dp)
                            .clip(CircleShape)
                            .background(DarkSurfaceElevated)
                            .border(2.dp, SafeGreen, CircleShape),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(text = "🧭", fontSize = 12.sp)
                            Text(
                                text = compass,
                                fontSize = 12.sp,
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
                .padding(horizontal = 12.dp, vertical = 6.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            item {
                FilterChip(
                    selected = selectedFilter == null,
                    onClick = { selectedFilter = null },
                    label = { Text("All (${amenities.size})", fontSize = 12.sp) },
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
                    label = { Text("${type.icon} ${type.label}", fontSize = 12.sp) },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = ActionBlue,
                        selectedLabelColor = Color.White
                    )
                )
            }
        }

        // --- VECTOR MAP CANVAS WITH PAN & ZOOM ---
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .background(DarkBackground)
        ) {
            Canvas(
                modifier = Modifier
                    .fillMaxSize()
                    // Tap gestures for selecting amenity pins
                    .pointerInput(filteredAmenities, mapCenterLat, mapCenterLng, zoomSpan) {
                        detectTapGestures { tapOffset ->
                            val w = size.width
                            val h = size.height

                            for (item in filteredAmenities) {
                                val x = ((item.lng - (mapCenterLng - zoomSpan / 2)) / zoomSpan * w).toFloat()
                                val y = (((mapCenterLat + zoomSpan / 2) - item.lat) / zoomSpan * h).toFloat()
                                val dist = hypot(tapOffset.x - x, tapOffset.y - y)
                                if (dist < 40f) {
                                    selectedAmenity = item
                                    onSelectAmenity(item)
                                    break
                                }
                            }
                        }
                    }
                    // Drag gestures to pan around the map
                    .pointerInput(zoomSpan) {
                        detectDragGestures { change, dragAmount ->
                            change.consume()
                            isFollowingGps = false
                            val w = size.width
                            val h = size.height
                            mapCenterLng -= (dragAmount.x / w) * zoomSpan
                            mapCenterLat += (dragAmount.y / h) * zoomSpan
                        }
                    }
            ) {
                val canvasWidth = size.width
                val canvasHeight = size.height

                fun toCanvasX(lng: Double): Float {
                    return ((lng - (mapCenterLng - zoomSpan / 2)) / zoomSpan * canvasWidth).toFloat()
                }

                fun toCanvasY(lat: Double): Float {
                    return (((mapCenterLat + zoomSpan / 2) - lat) / zoomSpan * canvasHeight).toFloat()
                }

                // 1. Draw subtle background tactical grid
                val gridColor = Color(0x18FFFFFF)
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
                            HazardStatus.CONTRADICTED -> ActionBlue
                            HazardStatus.CLEAR -> SafeGreen
                        }

                        drawPath(path, fillColor)
                        drawPath(path, strokeColor, style = Stroke(width = 2f))
                    }
                }

                // 3. Draw Escape Path Line to Nearest Shelter
                if (nearestShelter != null) {
                    val uX = toCanvasX(userLng)
                    val uY = toCanvasY(userLat)
                    val sX = toCanvasX(nearestShelter.lng)
                    val sY = toCanvasY(nearestShelter.lat)

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

                    if (isSelected) {
                        drawCircle(Color.White, radius = 18f, center = Offset(aX, aY))
                    }

                    drawCircle(Color(0xFF0F172A), radius = 13f, center = Offset(aX, aY))
                    drawCircle(pinColor, radius = 10f, center = Offset(aX, aY))
                    drawCircle(Color.White, radius = 3.5f, center = Offset(aX, aY))
                }

                // 5. Draw Real-time User Location
                val userX = toCanvasX(userLng)
                val userY = toCanvasY(userLat)

                // Draw live GPS Accuracy Radius if available
                if (gpsAccuracy > 0f) {
                    // Approx 111,000 meters per degree of latitude
                    val accuracyPixels = (gpsAccuracy / (zoomSpan * 111000.0) * canvasHeight).toFloat()
                    val radiusClamped = accuracyPixels.coerceIn(pulseRadius + 4f, canvasWidth * 0.45f)
                    drawCircle(
                        color = Color(0x223B82F6),
                        radius = radiusClamped,
                        center = Offset(userX, userY)
                    )
                    drawCircle(
                        color = Color(0x663B82F6),
                        radius = radiusClamped,
                        center = Offset(userX, userY),
                        style = Stroke(width = 1.5f)
                    )
                }

                // Draw Directional Bearing Cone if moving
                if (gpsSpeed > 0.4f || gpsBearing != 0f) {
                    val bearingRad = Math.toRadians((gpsBearing - 90).toDouble())
                    val coneLength = 36f
                    val beamX = userX + (cos(bearingRad) * coneLength).toFloat()
                    val beamY = userY + (sin(bearingRad) * coneLength).toFloat()
                    drawLine(
                        color = ActionBlue,
                        start = Offset(userX, userY),
                        end = Offset(beamX, beamY),
                        strokeWidth = 4f
                    )
                }

                // Radar pulse ring
                drawCircle(Color(0x553B82F6), radius = pulseRadius, center = Offset(userX, userY))
                // Dark border
                drawCircle(Color(0xFF0F172A), radius = 11f, center = Offset(userX, userY))
                // Bright Core (Solid Blue dot)
                drawCircle(ActionBlue, radius = 7.5f, center = Offset(userX, userY))
                drawCircle(Color.White, radius = 3.5f, center = Offset(userX, userY))
            }

            // Top HUD: Real-time Live GPS Coordinates & Status Pill
            Box(
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(top = 8.dp)
                    .clip(RoundedCornerShape(20.dp))
                    .background(Color(0xE60F172A))
                    .border(1.dp, if (isGpsLive) SafeGreen else DarkBorder, RoundedCornerShape(20.dp))
                    .padding(horizontal = 12.dp, vertical = 6.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(text = if (isGpsLive) "🟢" else "🟡", fontSize = 9.sp)
                    Text(
                        text = String.format(Locale.US, "%.5f°N, %.5f°E", userLat, userLng),
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                    if (gpsAccuracy > 0f) {
                        Text(
                            text = "· ±${gpsAccuracy.toInt()}m",
                            fontSize = 11.sp,
                            color = SafeGreen
                        )
                    }
                    if (gpsSpeed > 0.5f) {
                        Text(
                            text = "· ${(gpsSpeed * 3.6f).toInt()} km/h",
                            fontSize = 11.sp,
                            color = ActionBlue
                        )
                    }
                }
            }

            // Floating Controls: Recenter on Me & Zoom Controls (Right side)
            Column(
                modifier = Modifier
                    .align(Alignment.CenterEnd)
                    .padding(end = 12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // Recenter GPS Button
                FloatingActionButton(
                    onClick = {
                        mapCenterLat = userLat
                        mapCenterLng = userLng
                        isFollowingGps = true
                    },
                    modifier = Modifier.size(44.dp),
                    containerColor = if (isFollowingGps) ActionBlue else DarkSurfaceElevated,
                    contentColor = Color.White,
                    shape = CircleShape
                ) {
                    Text("🎯", fontSize = 18.sp)
                }

                // Zoom In Button (+)
                FloatingActionButton(
                    onClick = {
                        zoomSpan = (zoomSpan * 0.70).coerceAtLeast(0.005)
                    },
                    modifier = Modifier.size(40.dp),
                    containerColor = DarkSurfaceElevated,
                    contentColor = Color.White,
                    shape = CircleShape
                ) {
                    Text("+", fontSize = 20.sp, fontWeight = FontWeight.Bold)
                }

                // Zoom Out Button (-)
                FloatingActionButton(
                    onClick = {
                        zoomSpan = (zoomSpan * 1.40).coerceAtMost(0.18)
                    },
                    modifier = Modifier.size(40.dp),
                    containerColor = DarkSurfaceElevated,
                    contentColor = Color.White,
                    shape = CircleShape
                ) {
                    Text("-", fontSize = 20.sp, fontWeight = FontWeight.Bold)
                }
            }

            // Legend Overlay (Bottom Left)
            Box(
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .padding(8.dp)
                    .clip(RoundedCornerShape(6.dp))
                    .background(Color(0xD90F172A))
                    .padding(6.dp)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text("📍 Blue Dot: Real-time GPS", fontSize = 9.sp, color = ActionBlue, fontWeight = FontWeight.Bold)
                    Text("🛡️ Green Line: Safe Escape Path", fontSize = 9.sp, color = SafeGreen)
                    Text("🚨 Red: Flooded / Caution", fontSize = 9.sp, color = AlertRed)
                    Text("🟣 Purple: Safe Shelters", fontSize = 9.sp, color = PurpleReplay)
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
                    .background(DarkSurface)
                    .padding(14.dp)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(text = item.type.icon, fontSize = 22.sp)
                            Column {
                                Text(
                                    text = item.name,
                                    fontSize = 15.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color.White
                                )
                                Text(
                                    text = "${dist.toInt()}m away · Head $compass · ~$walkTime min walk",
                                    fontSize = 12.sp,
                                    color = SafeGreen,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }
                        }

                        IconButton(onClick = { selectedAmenity = null }) {
                            Text("✕", color = TextSecondary, fontSize = 16.sp)
                        }
                    }

                    if (item.suppliesAvailable.isNotEmpty()) {
                        Text(
                            text = "Supplies: ${item.suppliesAvailable.joinToString(" · ")}",
                            fontSize = 11.sp,
                            color = TextSecondary
                        )
                    }

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

                        TextButton(
                            onClick = { onSelectAmenity(item) }
                        ) {
                            Text("View in Amenities ➔", fontSize = 12.sp, color = ActionBlue)
                        }
                    }
                }
            }
        }
    }
}
