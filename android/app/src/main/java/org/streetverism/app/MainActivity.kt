package org.streetverism.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.streetverism.app.data.LocalAssetRepository
import org.streetverism.app.mesh.LocalMeshManager
import org.streetverism.app.model.Amenity
import org.streetverism.app.model.UserProfile
import org.streetverism.app.ui.components.IntuitiveCrisisMap
import org.streetverism.app.ui.screens.*
import org.streetverism.app.ui.theme.*

enum class AppTab(val label: String, val icon: String) {
    MAP("Crisis Map", "🗺️"),
    AMENITIES("Amenities", "🍲"),
    TRANSLATOR("Translator", "🗣️"),
    SAFETY("First Aid", "🩹"),
    MESH("P2P Mesh", "📡")
}

class MainActivity : ComponentActivity() {

    private lateinit var repository: LocalAssetRepository
    private val meshManager = LocalMeshManager.instance

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        repository = LocalAssetRepository(applicationContext)

        setContent {
            StreetVerismTheme {
                MainAppContainer(repository, meshManager)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainAppContainer(
    repository: LocalAssetRepository,
    meshManager: LocalMeshManager
) {
    var userProfile by remember { mutableStateOf(repository.getUserProfile()) }
    var showProfileModal by remember { mutableStateOf(userProfile == null) }
    var currentTab by remember { mutableStateOf(AppTab.MAP) }

    // Simulated / GPS coordinates (Adyar emergency zone demo location)
    val userLat by remember { mutableDoubleStateOf(13.015) }
    val userLng by remember { mutableDoubleStateOf(80.225) }

    // Pre-loaded offline datasets
    val amenities = remember { repository.getAmenities() }
    val phrases = remember { repository.getTranslationPhrases() }
    val (precautions, firstAidGuides) = remember { repository.getSafetyGuides() }
    val hazardZones = remember { repository.getHazardZones() }

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
                                .size(32.dp)
                                .clip(RoundedCornerShape(8.dp))
                                .background(ActionBlue),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("S", color = Color.White, fontWeight = FontWeight.Black, fontSize = 16.sp)
                        }

                        Column {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                Text(
                                    text = "StreetVerism",
                                    fontSize = 17.sp,
                                    fontWeight = FontWeight.ExtraBold,
                                    color = Color.White
                                )
                                Box(
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(4.dp))
                                        .background(Color(0x3510B981))
                                        .padding(horizontal = 5.dp, vertical = 2.dp)
                                ) {
                                    Text("OFFLINE", fontSize = 9.sp, fontWeight = FontWeight.Bold, color = SafeGreen)
                                }
                            }
                            Text(
                                text = "Zero-Network Crisis Companion",
                                fontSize = 11.sp,
                                color = TextSecondary
                            )
                        }
                    }
                },
                actions = {
                    // Profile button / avatar
                    Box(
                        modifier = Modifier
                            .padding(end = 12.dp)
                            .clip(RoundedCornerShape(16.dp))
                            .background(DarkSurfaceElevated)
                            .border(1.dp, if (userProfile?.isVulnerable() == true) AlertRed else ActionBlue, RoundedCornerShape(16.dp))
                            .clickable { showProfileModal = true }
                            .padding(horizontal = 10.dp, vertical = 5.dp)
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(text = "👤", fontSize = 12.sp)
                            Text(
                                text = userProfile?.name?.take(10) ?: "Profile",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color.White
                            )
                        }
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
                        icon = { Text(tab.icon, fontSize = 18.sp) },
                        label = { Text(tab.label, fontSize = 11.sp, fontWeight = if (currentTab == tab) FontWeight.Bold else FontWeight.Normal) },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = ActionBlue,
                            selectedTextColor = Color.White,
                            indicatorColor = DarkSurfaceElevated,
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
                    hazardZones = hazardZones,
                    amenities = amenities,
                    onSelectAmenity = { amenity ->
                        // Selected amenity handled within map bottom sheet
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
                        .background(Color(0xE6090D16))
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
