package org.streetverism.app

import android.Manifest
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import org.streetverism.app.data.LocalAssetRepository
import org.streetverism.app.location.GpsLocationManager
import org.streetverism.app.mesh.LocalMeshManager
import org.streetverism.app.model.Amenity
import org.streetverism.app.model.UserProfile
import org.streetverism.app.ui.components.IntuitiveCrisisMap
import org.streetverism.app.ui.screens.*
import org.streetverism.app.ui.theme.*

enum class AppTab(val label: String, val tag: String) {
    MAP("Crisis Map", "MAP"),
    AMENITIES("Amenities", "AID"),
    TRANSLATOR("Translator", "LANG"),
    SAFETY("First Aid", "CARE"),
    MESH("P2P Mesh", "MESH")
}

class MainActivity : ComponentActivity() {

    private lateinit var repository: LocalAssetRepository
    private val meshManager = LocalMeshManager.instance
    private lateinit var gpsLocationManager: GpsLocationManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        repository = LocalAssetRepository(applicationContext)
        gpsLocationManager = GpsLocationManager(applicationContext)

        setContent {
            StreetVerismTheme {
                MainAppContainer(repository, meshManager, gpsLocationManager)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainAppContainer(
    repository: LocalAssetRepository,
    meshManager: LocalMeshManager,
    gpsLocationManager: GpsLocationManager
) {
    var userProfile by remember { mutableStateOf(repository.getUserProfile()) }
    var showProfileModal by remember { mutableStateOf(userProfile == null) }
    var currentTab by remember { mutableStateOf(AppTab.MAP) }

    // Live GPS state flow from offline GPS hardware manager
    val gpsState by gpsLocationManager.gpsState.collectAsState()

    // Permission launcher for Fine & Coarse location
    val locationPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val fineGranted = permissions[Manifest.permission.ACCESS_FINE_LOCATION] ?: false
        val coarseGranted = permissions[Manifest.permission.ACCESS_COARSE_LOCATION] ?: false
        if (fineGranted || coarseGranted) {
            gpsLocationManager.startLocationUpdates()
        }
    }

    // Auto-prompt location permission and start GPS on launch
    LaunchedEffect(Unit) {
        if (gpsLocationManager.checkPermissions()) {
            gpsLocationManager.startLocationUpdates()
        } else {
            locationPermissionLauncher.launch(
                arrayOf(
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION
                )
            )
        }
    }

    // Lifecycle observer to save battery when backgrounded and resume when foregrounded
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                if (gpsLocationManager.checkPermissions()) {
                    gpsLocationManager.startLocationUpdates()
                }
            } else if (event == Lifecycle.Event.ON_PAUSE) {
                gpsLocationManager.stopLocationUpdates()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            gpsLocationManager.stopLocationUpdates()
        }
    }

    val userLat = gpsState.latitude
    val userLng = gpsState.longitude

    // Dynamically retrieve amenities and hazard zones for current GPS coordinates
    val amenities = remember(userLat, userLng) {
        repository.getAmenitiesForLocation(userLat, userLng)
    }
    val hazardZones = remember(userLat, userLng) {
        repository.getHazardZonesForLocation(userLat, userLng)
    }
    val phrases = remember { repository.getTranslationPhrases() }
    val (precautions, firstAidGuides) = remember { repository.getSafetyGuides() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(28.dp)
                                .clip(RoundedCornerShape(6.dp))
                                .background(ActionSlate),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("SV", color = Color.White, fontWeight = FontWeight.Black, fontSize = 12.sp)
                        }

                        Column {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                Text(
                                    text = "StreetVerism",
                                    fontSize = 16.sp,
                                    fontWeight = FontWeight.ExtraBold,
                                    color = Color.White
                                )
                                Box(
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(3.dp))
                                        .background(if (gpsState.isLive) SafeGreenSurface else ActionSlate)
                                        .padding(horizontal = 4.dp, vertical = 2.dp)
                                ) {
                                    Text(
                                        text = if (gpsState.isLive) "GPS LIVE" else "OFFLINE",
                                        fontSize = 8.sp,
                                        fontWeight = FontWeight.Black,
                                        color = if (gpsState.isLive) SafeGreen else Color.White
                                    )
                                }
                            }
                            Text(
                                text = "Zero-Network Crisis Companion",
                                fontSize = 10.sp,
                                color = TextSecondary
                            )
                        }
                    }
                },
                actions = {
                    // Live GPS Status Pill
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(4.dp))
                            .background(DarkSurfaceElevated)
                            .border(
                                1.dp,
                                if (gpsState.isLive) SafeGreen else if (!gpsState.hasPermission) AlertRed else CautionOrange,
                                RoundedCornerShape(4.dp)
                            )
                            .clickable {
                                if (!gpsState.hasPermission) {
                                    locationPermissionLauncher.launch(
                                        arrayOf(
                                            Manifest.permission.ACCESS_FINE_LOCATION,
                                            Manifest.permission.ACCESS_COARSE_LOCATION
                                        )
                                    )
                                } else if (!gpsState.isGpsEnabled) {
                                    gpsLocationManager.openLocationSettings()
                                }
                            }
                            .padding(horizontal = 8.dp, vertical = 4.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                            Box(
                                modifier = Modifier
                                    .size(6.dp)
                                    .clip(CircleShape)
                                    .background(if (gpsState.isLive) SafeGreen else if (!gpsState.hasPermission) AlertRed else CautionOrange)
                            )
                            Text(
                                text = if (!gpsState.hasPermission) {
                                    "Allow GPS"
                                } else if (!gpsState.isGpsEnabled) {
                                    "Enable GPS"
                                } else if (gpsState.isLive) {
                                    "GPS ±${gpsState.accuracy.toInt()}m"
                                } else {
                                    "Acquiring"
                                },
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold,
                                color = if (gpsState.isLive) SafeGreen else if (!gpsState.hasPermission) AlertRed else CautionOrange
                            )
                        }
                    }

                    Spacer(modifier = Modifier.width(6.dp))

                    // Profile button
                    Box(
                        modifier = Modifier
                            .padding(end = 12.dp)
                            .clip(RoundedCornerShape(4.dp))
                            .background(DarkSurfaceElevated)
                            .border(1.dp, if (userProfile?.isVulnerable() == true) AlertRed else DarkBorder, RoundedCornerShape(4.dp))
                            .clickable { showProfileModal = true }
                            .padding(horizontal = 8.dp, vertical = 4.dp)
                    ) {
                        Text(
                            text = "PROFILE: ${userProfile?.name?.take(8) ?: "SETUP"}",
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = DarkSurface
                )
            )
        },
        bottomBar = {
            NavigationBar(
                containerColor = DarkSurface,
                tonalElevation = 8.dp
            ) {
                AppTab.values().forEach { tab ->
                    NavigationBarItem(
                        selected = currentTab == tab,
                        onClick = { currentTab = tab },
                        icon = {
                            Box(
                                modifier = Modifier
                                    .size(24.dp)
                                    .clip(RoundedCornerShape(4.dp))
                                    .background(if (currentTab == tab) ActionSlateActive else DarkSurfaceElevated),
                                contentAlignment = Alignment.Center
                            ) {
                                Text(
                                    text = tab.tag,
                                    fontSize = 8.sp,
                                    fontWeight = FontWeight.Black,
                                    color = if (currentTab == tab) Color.White else TextMuted
                                )
                            }
                        },
                        label = { Text(tab.label, fontSize = 10.sp, fontWeight = if (currentTab == tab) FontWeight.Bold else FontWeight.Normal) },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = Color.White,
                            selectedTextColor = Color.White,
                            indicatorColor = ActionSlate,
                            unselectedTextColor = TextMuted
                        )
                    )
                }
            }
        }
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
        ) {
            when (currentTab) {
                AppTab.MAP -> IntuitiveCrisisMap(
                    userLat = userLat,
                    userLng = userLng,
                    gpsAccuracy = gpsState.accuracy,
                    gpsBearing = gpsState.bearing,
                    gpsSpeed = gpsState.speed,
                    isGpsLive = gpsState.isLive,
                    gpsStatusMessage = gpsState.statusMessage,
                    hazardZones = hazardZones,
                    amenities = amenities,
                    onSelectAmenity = {
                        // Handled within map bottom sheet
                    }
                )
                AppTab.AMENITIES -> AmenitiesScreen(
                    userLat = userLat,
                    userLng = userLng,
                    amenities = amenities,
                    onNavigateToAmenityOnMap = {
                        currentTab = AppTab.MAP
                    }
                )
                AppTab.TRANSLATOR -> TranslatorScreen(
                    userLanguage = userProfile?.language ?: "en",
                    phrases = phrases
                )
                AppTab.SAFETY -> SafetyGuideScreen(
                    precautions = precautions,
                    firstAidGuides = firstAidGuides
                )
                AppTab.MESH -> OfflineMeshScreen(
                    userProfile = userProfile ?: UserProfile("Tourist", 25, "en", "International"),
                    userLat = userLat,
                    userLng = userLng,
                    meshManager = meshManager
                )
            }

            // Profile Setup Modal (shown on first launch or when profile badge tapped)
            if (showProfileModal) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(Color(0xF0090A0C))
                ) {
                    ProfileScreen(
                        currentProfile = userProfile,
                        onSaveProfile = { newProfile ->
                            repository.saveUserProfile(newProfile)
                            userProfile = newProfile
                            showProfileModal = false
                        }
                    )
                }
            }
        }
    }
}
