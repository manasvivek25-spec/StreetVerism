package org.streetverism.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import org.streetverism.app.mesh.LocalMeshManager
import org.streetverism.app.mesh.MeshPacketType
import org.streetverism.app.model.UserProfile
import org.streetverism.app.ui.theme.*

@Composable
fun OfflineMeshScreen(
    userProfile: UserProfile,
    userLat: Double,
    userLng: Double,
    meshManager: LocalMeshManager
) {
    val meshState by meshManager.meshState.collectAsState()

    var selectedClaim by remember { mutableStateOf("flooded") }
    var reportNote by remember { mutableStateOf("") }
    var statusFeedback by remember { mutableStateOf<String?>(null) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        // Title
        Column {
            Text(
                text = "P2P Offline Crisis Mesh",
                fontSize = 20.sp,
                fontWeight = FontWeight.ExtraBold,
                color = Color.White
            )
            Text(
                text = "Broadcast check-ins and hazard reports peer-to-peer without cell towers.",
                fontSize = 12.sp,
                color = TextSecondary
            )
        }

        // Live Mesh Status Banner
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .background(DarkSurfaceElevated)
                .border(1.dp, SafeGreen, RoundedCornerShape(10.dp))
                .padding(12.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("🟢", fontSize = 12.sp)
                        Text(
                            text = "LOCAL MESH ACTIVE (ZERO NETWORK)",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Black,
                            color = SafeGreen
                        )
                    }
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        text = "${meshState.connectedPeerCount} nearby smartphones in direct range",
                        fontSize = 12.sp,
                        color = Color.White
                    )
                }

                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(6.dp))
                        .background(Color(0x3010B981))
                        .padding(horizontal = 8.dp, vertical = 4.dp)
                ) {
                    Text(text = "BLE / Ad-Hoc", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = SafeGreen)
                }
            }
        }

        // 1-Tap Emergency Check-in Buttons
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                text = "1-TAP CRISIS STATUS CHECK-IN",
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                color = TextSecondary
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Button(
                    onClick = {
                        val packet = meshManager.broadcastCheckIn(
                            profile = userProfile,
                            lat = userLat,
                            lng = userLng,
                            isSafe = true,
                            note = "Safe at high ground"
                        )
                        statusFeedback = "✓ Broadcasted 'SAFE' packet #${packet.packetId} to local swarm"
                    },
                    modifier = Modifier
                        .weight(1f)
                        .height(48.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = SafeGreen),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text("✓ I Am Safe", fontWeight = FontWeight.Bold, color = Color.White)
                }

                Button(
                    onClick = {
                        val packet = meshManager.broadcastCheckIn(
                            profile = userProfile,
                            lat = userLat,
                            lng = userLng,
                            isSafe = false,
                            note = "URGENT: Evacuation needed for ${userProfile.name} (Age ${userProfile.age})"
                        )
                        statusFeedback = "🚨 Broadcasted RESCUE REQUEST #${packet.packetId} (Priority: ${userProfile.vulnerabilityTier()})"
                    },
                    modifier = Modifier
                        .weight(1f)
                        .height(48.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = AlertRed),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text("🚨 I Need Help", fontWeight = FontWeight.Bold, color = Color.White)
                }
            }
        }

        // Community Hazard Report Input
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .background(DarkSurface)
                .border(1.dp, DarkBorder, RoundedCornerShape(10.dp))
                .padding(12.dp)
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    text = "REPORT LOCAL HAZARD (OFFLINE SWARM)",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    color = ActionBlue
                )

                // Claim Radios
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    listOf(
                        Pair("flooded", "🌊 Flooded"),
                        Pair("blocked", "🚧 Blocked"),
                        Pair("safe", "🛡️ Clear")
                    ).forEach { (claimKey, claimLabel) ->
                        FilterChip(
                            selected = selectedClaim == claimKey,
                            onClick = { selectedClaim = claimKey },
                            label = { Text(claimLabel, fontSize = 11.sp) },
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = ActionBlue,
                                selectedLabelColor = Color.White
                            )
                        )
                    }
                }

                OutlinedTextField(
                    value = reportNote,
                    onValueChange = { reportNote = it },
                    placeholder = { Text("Water depth, landmark, street name...", color = TextMuted) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = Color.White,
                        unfocusedTextColor = Color.White,
                        focusedBorderColor = ActionBlue,
                        unfocusedBorderColor = DarkBorder,
                        focusedContainerColor = DarkSurfaceElevated,
                        unfocusedContainerColor = DarkSurfaceElevated
                    )
                )

                Button(
                    onClick = {
                        val packet = meshManager.broadcastHazardReport(
                            profile = userProfile,
                            lat = userLat,
                            lng = userLng,
                            claim = selectedClaim,
                            details = reportNote
                        )
                        statusFeedback = "Broadcasted hazard report #${packet.packetId} over P2P mesh"
                        reportNote = ""
                    },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = ActionBlue),
                    shape = RoundedCornerShape(6.dp)
                ) {
                    Text("Broadcast Report Over Mesh", fontWeight = FontWeight.Bold, color = Color.White)
                }
            }
        }

        if (statusFeedback != null) {
            Text(
                text = statusFeedback!!,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                color = SafeGreen
            )
        }

        // Swarm Packet Feed
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = "STORE & FORWARD MESH PACKET FEED (${meshState.localPackets.size + meshState.receivedRelayedPackets.size})",
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                color = TextSecondary,
                modifier = Modifier.padding(bottom = 6.dp)
            )

            val allPackets = meshState.localPackets + meshState.receivedRelayedPackets

            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(allPackets) { packet ->
                    val badgeColor = when (packet.packetType) {
                        MeshPacketType.CHECKIN_HELP -> AlertRed
                        MeshPacketType.CHECKIN_SAFE -> SafeGreen
                        MeshPacketType.HAZARD_REPORT -> WarningYellow
                    }

                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .background(DarkSurfaceElevated)
                            .border(1.dp, if (packet.packetType == MeshPacketType.CHECKIN_HELP) AlertRed else DarkBorder, RoundedCornerShape(8.dp))
                            .padding(10.dp)
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "${packet.senderName} (${packet.senderNationality}, Age ${packet.senderAge})",
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color.White
                                )

                                Text(
                                    text = if (packet.isRelayed) "Relayed (Hop ${packet.hopCount})" else "Local Origin",
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = if (packet.isRelayed) ActionBlue else SafeGreen
                                )
                            }

                            Text(
                                text = packet.note,
                                fontSize = 12.sp,
                                color = TextPrimary
                            )

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    text = "GPS: ${String.format("%.4f", packet.lat)}, ${String.format("%.4f", packet.lng)}",
                                    fontSize = 10.sp,
                                    color = TextMuted
                                )
                                Text(
                                    text = "ID: #${packet.packetId}",
                                    fontSize = 10.sp,
                                    color = TextMuted
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
