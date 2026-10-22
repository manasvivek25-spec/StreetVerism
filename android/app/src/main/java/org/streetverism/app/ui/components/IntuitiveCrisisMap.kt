package org.streetverism.app.ui.components

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
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
import androidx.compose.ui.geometry.Size
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

    // Map viewport state: center coordinates and zoom level
    var mapCenterLat by remember { mutableDoubleStateOf(userLat) }
    var mapCenterLng by remember { mutableDoubleStateOf(userLng) }
    var zoomSpan by remember { mutableDoubleStateOf(0.015) } // Default ~1.5km street-level view (like Google Maps)
    var isFollowingGps by remember { mutableStateOf(true) }

    // Dynamically target nearest safe shelter or user-selected facility for navigation path
    val defaultTargetShelter = remember(userLat, userLng, amenities) {
        amenities.filter { it.type == AmenityType.SHELTER }
            .minByOrNull { it.distanceMetersTo(userLat, userLng) }
    }
    var activeNavigationTarget by remember { mutableStateOf<Amenity?>(null) }
    val currentRouteTarget = activeNavigationTarget ?: defaultTargetShelter

    // Keep map centered on user's live GPS coordinates when in follow mode
    LaunchedEffect(userLat, userLng, isFollowingGps) {
        if (isFollowingGps) {
            mapCenterLat = userLat
            mapCenterLng = userLng
        }
    }

    val filteredAmenities = remember(selectedFilter, amenities) {
        if (selectedFilter == null) amenities else amenities.filter { it.type == selectedFilter }
    }

    // Subtle breathing pulse for user position puck
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val pulseRadius by infiniteTransition.animateFloat(
        initialValue = 12f,
        targetValue = 26f,
        animationSpec = infiniteRepeatable(
            animation = tween(1400, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "pulseRadius"
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
    ) {
        // --- GOOGLE MAPS STYLE TURN-BY-TURN NAVIGATION BANNER ---
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(DarkSurface)
                .border(width = 1.dp, color = DarkBorder)
                .padding(horizontal = 16.dp, vertical = 12.dp)
        ) {
            if (currentRouteTarget != null) {
                val distM = currentRouteTarget.distanceMetersTo(userLat, userLng)
                val compass = currentRouteTarget.compassDirectionFrom(userLat, userLng)
                val walkMins = max(1, (distM / 75.0).toInt())

                val arrowSymbol = when (compass) {
                    "N" -> "↑"
                    "NE" -> "↗"
                    "E" -> "→"
                    "SE" -> "↘"
                    "S" -> "↓"
                    "SW" -> "↙"
                    "W" -> "←"
                    "NW" -> "↖"
                    else -> "↑"
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    // Turn arrow in dark tactical container
                    Box(
                        modifier = Modifier
                            .size(46.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(DarkSurfaceElevated)
                            .border(1.dp, SafeGreen, RoundedCornerShape(8.dp)),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = arrowSymbol,
                            fontSize = 24.sp,
                            fontWeight = FontWeight.Black,
                            color = SafeGreen
                        )
                    }

                    Spacer(modifier = Modifier.width(12.dp))

                    Column(modifier = Modifier.weight(1f)) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(
                                text = "HEAD $compass",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Black,
                                color = TextSecondary,
                                letterSpacing = 1.sp
                            )
                            Text(
                                text = "· SAFE ROUTE",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = SafeGreen
                            )
                        }

                        Text(
                            text = currentRouteTarget.name,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White,
                            maxLines = 1
                        )

                        Text(
                            text = "${distM.toInt()} m (${walkMins} min walk) · ${currentRouteTarget.address}",
                            fontSize = 12.sp,
                            color = TextMuted,
                            maxLines = 1
                        )
                    }

                    // ETA / Distance Badge
                    Column(horizontalAlignment = Alignment.End) {
                        Text(
                            text = "${distM.toInt()}m",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.ExtraBold,
                            color = SafeGreen
                        )
                        Text(
                            text = "${walkMins} min",
                            fontSize = 11.sp,
                            color = TextSecondary
                        )
                    }
                }
            } else {
                Text(
                    text = "Searching safe evacuation route...",
                    fontSize = 13.sp,
                    color = TextSecondary
                )
            }
        }

        // --- FILTER CHIPS (CLEAN MONOCHROME/GREY) ---
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
                    label = { Text("All (${amenities.size})", fontSize = 12.sp, fontWeight = FontWeight.Bold) },
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
                    selected = selectedFilter == type,
                    onClick = { selectedFilter = type },
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

        // --- GOOGLE MAPS STYLE CANVAS (PINCH-TO-ZOOM, PAN, STREET GRID, ROUTE) ---
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .background(MapLand)
        ) {
            Canvas(
                modifier = Modifier
                    .fillMaxSize()
                    // 1. Fluid Multi-Touch Pinch-to-Zoom and Two-Finger Pan (Google Maps feel)
                    .pointerInput(Unit) {
                        detectTransformGestures { _, pan, zoom, _ ->
                            zoomSpan = (zoomSpan / zoom).coerceIn(0.0025, 0.12)
                            val w = size.width
                            val h = size.height
                            mapCenterLng -= (pan.x / w) * zoomSpan
                            mapCenterLat += (pan.y / h) * zoomSpan
                            isFollowingGps = false
                        }
                    }
                    // 2. Tap to select amenity pins
                    .pointerInput(filteredAmenities, mapCenterLat, mapCenterLng, zoomSpan) {
                        detectTapGestures { tapOffset ->
                            val w = size.width
                            val h = size.height

                            for (item in filteredAmenities) {
                                val x = ((item.lng - (mapCenterLng - zoomSpan / 2)) / zoomSpan * w).toFloat()
                                val y = (((mapCenterLat + zoomSpan / 2) - item.lat) / zoomSpan * h).toFloat()
                                val dist = hypot(tapOffset.x - x, tapOffset.y - y)
                                if (dist < 38f) {
                                    activeNavigationTarget = item
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
                    return ((lng - (mapCenterLng - zoomSpan / 2)) / zoomSpan * canvasWidth).toFloat()
                }

                fun toCanvasY(lat: Double): Float {
                    return (((mapCenterLat + zoomSpan / 2) - lat) / zoomSpan * canvasHeight).toFloat()
                }

                // -------------------------------------------------------------
                // 1. BASE MAP LAYER: Realistic Street Grid & City Blocks
                // -------------------------------------------------------------
                // Draw structured city parcels
                val blockCols = 10
                val blockRows = 12
                val blockW = canvasWidth / blockCols
                val blockH = canvasHeight / blockRows

                for (r in 0 until blockRows) {
                    for (c in 0 until blockCols) {
                        drawRect(
                            color = MapBlock,
                            topLeft = Offset(c * blockW + 3f, r * blockH + 3f),
                            size = Size(blockW - 6f, blockH - 6f)
                        )
                    }
                }

                // Secondary Streets (Crossroads)
                for (r in 0..blockRows) {
                    val y = r * blockH
                    drawLine(MapRoadSecondary, Offset(0f, y), Offset(canvasWidth, y), strokeWidth = 3f)
                }
                for (c in 0..blockCols) {
                    val x = c * blockW
                    drawLine(MapRoadSecondary, Offset(x, 0f), Offset(x, canvasHeight), strokeWidth = 3f)
                }

                // Primary Arterial Roads (Dual-cased prominent avenues)
                val primaryRow1 = (blockRows / 3) * blockH
                val primaryRow2 = (2 * blockRows / 3) * blockH
                val primaryCol1 = (blockCols / 3) * blockW
                val primaryCol2 = (2 * blockCols / 3) * blockW

                // Road Casings (Dark borders)
                drawLine(MapRoadCasing, Offset(0f, primaryRow1), Offset(canvasWidth, primaryRow1), strokeWidth = 10f)
                drawLine(MapRoadCasing, Offset(0f, primaryRow2), Offset(canvasWidth, primaryRow2), strokeWidth = 10f)
                drawLine(MapRoadCasing, Offset(primaryCol1, 0f), Offset(primaryCol1, canvasHeight), strokeWidth = 10f)
                drawLine(MapRoadCasing, Offset(primaryCol2, 0f), Offset(primaryCol2, canvasHeight), strokeWidth = 10f)

                // Road Infill
                drawLine(MapRoadPrimary, Offset(0f, primaryRow1), Offset(canvasWidth, primaryRow1), strokeWidth = 7f)
                drawLine(MapRoadPrimary, Offset(0f, primaryRow2), Offset(canvasWidth, primaryRow2), strokeWidth = 7f)
                drawLine(MapRoadPrimary, Offset(primaryCol1, 0f), Offset(primaryCol1, canvasHeight), strokeWidth = 7f)
                drawLine(MapRoadPrimary, Offset(primaryCol2, 0f), Offset(primaryCol2, canvasHeight), strokeWidth = 7f)

                // -------------------------------------------------------------
                // 2. VECTOR HAZARD / FLOOD ZONES
                // -------------------------------------------------------------
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
                            HazardStatus.OFFICIAL_HAZARD -> Color(0x35DC2626)
                            HazardStatus.LIKELY_HAZARD -> Color(0x28EA580C)
                            HazardStatus.UNVERIFIED -> Color(0x20D97706)
                            HazardStatus.CONTRADICTED -> Color(0x20334155)
                            HazardStatus.CLEAR -> Color(0x2016A34A)
                        }

                        val strokeColor = when (zone.status) {
                            HazardStatus.OFFICIAL_HAZARD -> AlertRed
                            HazardStatus.LIKELY_HAZARD -> CautionOrange
                            HazardStatus.UNVERIFIED -> WarningYellow
                            HazardStatus.CONTRADICTED -> ActionSlateActive
                            HazardStatus.CLEAR -> SafeGreen
                        }

                        drawPath(path, fillColor)
                        drawPath(path, strokeColor, style = Stroke(width = 2.5f))
                    }
                }

                // -------------------------------------------------------------
                // 3. GOOGLE MAPS NAVIGATION ROUTE POLYLINE TO TARGET
                // -------------------------------------------------------------
                if (currentRouteTarget != null) {
                    val uX = toCanvasX(userLng)
                    val uY = toCanvasY(userLat)
                    val tX = toCanvasX(currentRouteTarget.lng)
                    val tY = toCanvasY(currentRouteTarget.lat)

                    // Draw route with a waypoint turn following the street grid
                    val midX = tX
                    val midY = uY

                    val routePath = Path().apply {
                        moveTo(uX, uY)
                        lineTo(midX, midY)
                        lineTo(tX, tY)
                    }

                    // Outer dark casing for route contrast
                    drawPath(
                        path = routePath,
                        color = MapRouteCasing,
                        style = Stroke(width = 8f)
                    )
                    // Inner bright green route line
                    drawPath(
                        path = routePath,
                        color = MapRoutePath,
                        style = Stroke(width = 5f)
                    )

                    // Directional chevrons along path
                    val seg1Len = abs(midX - uX)
                    val seg2Len = abs(tY - midY)
                    val step = 45f

                    // Horizontal segment arrows
                    if (seg1Len > 30f) {
                        val dir = if (midX > uX) 1 else -1
                        var curr = uX + (dir * 25f)
                        while (abs(curr - uX) < seg1Len - 15f) {
                            drawCircle(Color.White, radius = 2.5f, center = Offset(curr, uY))
                            curr += dir * step
                        }
                    }
                    // Vertical segment arrows
                    if (seg2Len > 30f) {
                        val dir = if (tY > midY) 1 else -1
                        var curr = midY + (dir * 25f)
                        while (abs(curr - midY) < seg2Len - 15f) {
                            drawCircle(Color.White, radius = 2.5f, center = Offset(tX, curr))
                            curr += dir * step
                        }
                    }
                }

                // -------------------------------------------------------------
                // 4. GOOGLE MAPS STYLE AMENITY TEARDROP PINS (NO EMOJIS)
                // -------------------------------------------------------------
                for (item in filteredAmenities) {
                    val aX = toCanvasX(item.lng)
                    val aY = toCanvasY(item.lat)
                    val isSelected = currentRouteTarget?.id == item.id

                    val pinColor = when (item.type) {
                        AmenityType.HOSPITAL -> AlertRed
                        AmenityType.PHARMACY -> SafeGreen
                        AmenityType.FOOD_WATER -> Color(0xFF64748B) // Slate grey
                        AmenityType.FIRST_AID -> WarningYellow
                        AmenityType.SHELTER -> Color(0xFFCBD5E1) // Clean silver off-white
                    }

                    // Outer glow if selected
                    if (isSelected) {
                        drawCircle(Color.White, radius = 17f, center = Offset(aX, aY))
                    }

                    // Teardrop / Circular Marker Pin
                    drawCircle(Color(0xFF090A0C), radius = 13f, center = Offset(aX, aY))
                    drawCircle(pinColor, radius = 10f, center = Offset(aX, aY))
                    drawCircle(Color(0xFF090A0C), radius = 4f, center = Offset(aX, aY))
                }

                // -------------------------------------------------------------
                // 5. GOOGLE MAPS STYLE USER LOCATION PUCK WITH BEARING CONE
                // -------------------------------------------------------------
                val userX = toCanvasX(userLng)
                val userY = toCanvasY(userLat)

                // Live GPS Accuracy Radius Ring
                if (gpsAccuracy > 0f) {
                    val accuracyPixels = (gpsAccuracy / (zoomSpan * 111000.0) * canvasHeight).toFloat()
                    val radiusClamped = accuracyPixels.coerceIn(pulseRadius + 4f, canvasWidth * 0.40f)
                    drawCircle(
                        color = Color(0x1538BDF8),
                        radius = radiusClamped,
                        center = Offset(userX, userY)
                    )
                    drawCircle(
                        color = Color(0x5038BDF8),
                        radius = radiusClamped,
                        center = Offset(userX, userY),
                        style = Stroke(width = 1.5f)
                    )
                }

                // Forward Heading Cone
                if (gpsBearing != 0f || gpsSpeed > 0.4f) {
                    val bearingRad = Math.toRadians((gpsBearing - 90).toDouble())
                    val coneLength = 34f
                    val beamX = userX + (cos(bearingRad) * coneLength).toFloat()
                    val beamY = userY + (sin(bearingRad) * coneLength).toFloat()
                    drawLine(
                        color = Color(0xFF38BDF8),
                        start = Offset(userX, userY),
                        end = Offset(beamX, beamY),
                        strokeWidth = 3f
                    )
                }

                // Radar pulse ring
                drawCircle(Color(0x3538BDF8), radius = pulseRadius, center = Offset(userX, userY))
                // White rim (Google Maps puck style)
                drawCircle(Color.White, radius = 10f, center = Offset(userX, userY))
                // Slate core
                drawCircle(Color(0xFF0284C7), radius = 7f, center = Offset(userX, userY))
                // Center white dot
                drawCircle(Color.White, radius = 2.5f, center = Offset(userX, userY))
            }

            // Top HUD: Real-time Live GPS Coordinates & Status Pill
            Box(
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(top = 8.dp)
                    .clip(RoundedCornerShape(4.dp))
                    .background(Color(0xF0111418))
                    .border(1.dp, if (isGpsLive) SafeGreen else DarkBorder, RoundedCornerShape(4.dp))
                    .padding(horizontal = 10.dp, vertical = 5.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Box(
                        modifier = Modifier
                            .size(6.dp)
                            .clip(CircleShape)
                            .background(if (isGpsLive) SafeGreen else WarningYellow)
                    )
                    Text(
                        text = String.format(Locale.US, "%.5f°N, %.5f°E", userLat, userLng),
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                    if (gpsAccuracy > 0f) {
                        Text(
                            text = "±${gpsAccuracy.toInt()}m",
                            fontSize = 11.sp,
                            color = TextSecondary
                        )
                    }
                    if (gpsSpeed > 0.5f) {
                        Text(
                            text = "${(gpsSpeed * 3.6f).toInt()} km/h",
                            fontSize = 11.sp,
                            color = SafeGreen
                        )
                    }
                }
            }

            // Google Maps Style Floating Controls: Recenter and Zoom +/- (Bottom Right)
            Column(
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .padding(end = 12.dp, bottom = 12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // Recenter My Location Button (Google Maps crosshair style)
                FloatingActionButton(
                    onClick = {
                        mapCenterLat = userLat
                        mapCenterLng = userLng
                        isFollowingGps = true
                    },
                    modifier = Modifier.size(44.dp),
                    containerColor = if (isFollowingGps) DarkSurfaceElevated else DarkSurface,
                    contentColor = if (isFollowingGps) SafeGreen else Color.White,
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text("⌖", fontSize = 22.sp, fontWeight = FontWeight.Black)
                }

                // Zoom In (+)
                FloatingActionButton(
                    onClick = {
                        zoomSpan = (zoomSpan * 0.70).coerceAtLeast(0.0025)
                    },
                    modifier = Modifier.size(40.dp),
                    containerColor = DarkSurface,
                    contentColor = Color.White,
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text("+", fontSize = 22.sp, fontWeight = FontWeight.Bold)
                }

                // Zoom Out (−)
                FloatingActionButton(
                    onClick = {
                        zoomSpan = (zoomSpan * 1.40).coerceAtMost(0.12)
                    },
                    modifier = Modifier.size(40.dp),
                    containerColor = DarkSurface,
                    contentColor = Color.White,
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text("−", fontSize = 22.sp, fontWeight = FontWeight.Bold)
                }
            }

            // Tactical Legend (Bottom Left)
            Box(
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .padding(8.dp)
                    .clip(RoundedCornerShape(4.dp))
                    .background(Color(0xF0111418))
                    .border(1.dp, DarkBorder, RoundedCornerShape(4.dp))
                    .padding(6.dp)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text("Puck: Live GPS", fontSize = 9.sp, color = Color.White, fontWeight = FontWeight.Bold)
                    Text("Green Line: Safe Evacuation Path", fontSize = 9.sp, color = SafeGreen)
                    Text("Red Zone: Inundation Hazard", fontSize = 9.sp, color = AlertRed)
                    Text("Pins: [SAFE] [FOOD] [PHARM] [HOSP]", fontSize = 8.sp, color = TextMuted)
                }
            }
        }

        // --- SELECTED AMENITY BOTTOM SHEET / ACTION CARD ---
        if (currentRouteTarget != null) {
            val item = currentRouteTarget
            val dist = item.distanceMetersTo(userLat, userLng)
            val compass = item.compassDirectionFrom(userLat, userLng)
            val walkTime = max(1, (dist / 75.0).toInt())

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(DarkSurface)
                    .border(1.dp, DarkBorder)
                    .padding(14.dp)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                Box(
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(3.dp))
                                        .background(ActionSlate)
                                        .padding(horizontal = 4.dp, vertical = 2.dp)
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
                                text = "${dist.toInt()}m away · Head $compass · ~$walkTime min walk",
                                fontSize = 12.sp,
                                color = SafeGreen,
                                fontWeight = FontWeight.SemiBold
                            )
                        }

                        // Status Tag
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(if (item.is24x7) SafeGreenSurface else AlertRedSurface)
                                .padding(horizontal = 6.dp, vertical = 3.dp)
                        ) {
                            Text(
                                text = if (item.is24x7) "24x7 OPEN" else "LIMITED HOURS",
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold,
                                color = if (item.is24x7) SafeGreen else CautionOrange
                            )
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
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Button(
                            onClick = {
                                activeNavigationTarget = item
                                mapCenterLat = item.lat
                                mapCenterLng = item.lng
                                isFollowingGps = false
                            },
                            modifier = Modifier
                                .weight(1f)
                                .height(38.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = ActionSlate),
                            shape = RoundedCornerShape(6.dp)
                        ) {
                            Text("Follow Path", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = Color.White)
                        }

                        Button(
                            onClick = { onSelectAmenity(item) },
                            modifier = Modifier
                                .weight(1f)
                                .height(38.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = DarkSurfaceElevated),
                            shape = RoundedCornerShape(6.dp)
                        ) {
                            Text("Full Details", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = TextPrimary)
                        }
                    }
                }
            }
        }
    }
}
