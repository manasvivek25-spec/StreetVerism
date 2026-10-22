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
                text = "P2P ZERO-NETWORK CRISIS MESH",
                fontSize = 18.sp,
                fontWeight = FontWeight.Black,
                color = Color.White,
                letterSpacing = 0.5.sp
            )
            Text(
                text = "Direct device-to-device radio broadcasts over BLE / Wi-Fi ad-hoc without cellular infrastructure.",
                fontSize = 12.sp,
                color = TextSecondary
            )
        }

        // Live Mesh Status Banner (Tactical Dark Slate)
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(8.dp))
                .background(DarkSurfaceElevated)
                .border(1.dp, SafeGreen, RoundedCornerShape(8.dp))
                .padding(12.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Box(
                            modifier = Modifier
                                .size(6.dp)
                                .clip(RoundedCornerShape(3.dp))
                                .background(SafeGreen)
                        )
                        Text(
                            text = "OFFLINE MESH ACTIVE",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Black,
                            color = SafeGreen
                        )
                    }
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        text = "${meshState.connectedPeerCount} nearby devices in direct transmission range",
                        fontSize = 12.sp,
                        color = Color.White
                    )
                }

                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(4.dp))
                        .background(ActionSlate)
                        .padding(horizontal = 8.dp, vertical = 4.dp)
                ) {
                    Text(text = "BLE / Direct", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = Color.White)
                }
            }
        }

        // 1-Tap Emergency Check-in Buttons
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "STATUS BROADCAST BEACON",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    color = TextSecondary
                )
                Text(
                    text = String.format(java.util.Locale.US, "GPS: %.4f, %.4f", userLat, userLng),
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    color = SafeGreen
                )
            }

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
                        statusFeedback = "Dispatched SAFE packet #${packet.packetId} to local swarm"
                    },
                    modifier = Modifier
                        .weight(1f)
                        .height(46.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = SafeGreen),
                    shape = RoundedCornerShape(6.dp)
                ) {
                    Text("STATUS: SAFE", fontWeight = FontWeight.Bold, color = Color.White, fontSize = 12.sp)
                }

                Button(
                    onClick = {
                        val packet = meshManager.broadcastCheckIn(
                            profile = userProfile,
                            lat = userLat,
                            lng = userLng,
                            isSafe = false,
                            note = "EVACUATION: Required for ${userProfile.name} (Age ${userProfile.age})"
                        )
                        statusFeedback = "Dispatched SOS REQUEST #${packet.packetId} (Priority: ${userProfile.vulnerabilityTier()})"
                    },
                    modifier = Modifier
                        .weight(1f)
                        .height(46.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = AlertRed),
                    shape = RoundedCornerShape(6.dp)
                ) {
                    Text("BROADCAST SOS", fontWeight = FontWeight.Bold, color = Color.White, fontSize = 12.sp)
                }
            }
        }

        // Community Hazard Report Input
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(8.dp))
                .background(DarkSurface)
                .border(1.dp, DarkBorder, RoundedCornerShape(8.dp))
                .padding(12.dp)
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    text = "REPORT LOCAL SECTOR HAZARD",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    color = TextSecondary
                )

                // Claim Radios (Tactical labels)
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    listOf(
                        Pair("flooded", "INUNDATED"),
                        Pair("blocked", "BLOCKED ROAD"),
                        Pair("safe", "CLEAR PASSAGE")
                    ).forEach { (claimKey, claimLabel) ->
                        FilterChip(
                            selected = selectedClaim == claimKey,
                            onClick = { selectedClaim = claimKey },
                            label = { Text(claimLabel, fontSize = 10.sp, fontWeight = FontWeight.Bold) },
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = ActionSlateActive,
                                selectedLabelColor = Color.White,
                                containerColor = DarkSurfaceElevated,
                                labelColor = TextSecondary
                            ),
                            shape = RoundedCornerShape(4.dp)
                        )
                    }
                }

                OutlinedTextField(
                    value = reportNote,
                    onValueChange = { reportNote = it },
                    placeholder = { Text("Water depth, landmark, street obstacle...", color = TextMuted, fontSize = 12.sp) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = Color.White,
                        unfocusedTextColor = Color.White,
                        focusedBorderColor = ActionSlateActive,
                        unfocusedBorderColor = DarkBorder,
                        focusedContainerColor = DarkSurfaceElevated,
                        unfocusedContainerColor = DarkSurfaceElevated
                    ),
                    shape = RoundedCornerShape(6.dp)
                )

                Button(
                    onClick = {
                        val packet = meshManager.broadcastHazardReport(
                            profile = userProfile,
                            lat = userLat,
                            lng = userLng,
                            claim = selectedClaim,
                            details = reportNote.ifBlank { "Hazard reported in sector" }
                        )
                        reportNote = ""
                        statusFeedback = "Hazard observation #${packet.packetId} broadcasted to mesh"
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(40.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = ActionSlate),
                    shape = RoundedCornerShape(6.dp)
                ) {
                    Text("Broadcast Observation to Swarm", fontWeight = FontWeight.Bold, fontSize = 12.sp)
                }

                if (statusFeedback != null) {
                    Text(
                        text = statusFeedback!!,
                        fontSize = 11.sp,
                        color = SafeGreen,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
        }

        // Live Swarm Packets Feed
        val allPackets = remember(meshState) {
            meshState.localPackets + meshState.receivedRelayedPackets
        }

        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = "SWARM PACKET INBOX (${allPackets.size})",
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                color = TextSecondary
            )

            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(allPackets) { packet ->
                    val isSos = packet.packetType == MeshPacketType.CHECKIN_HELP
                    val isSafe = packet.packetType == MeshPacketType.CHECKIN_SAFE

                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(6.dp))
                            .background(DarkSurfaceElevated)
                            .border(
                                1.dp,
                                if (isSos) AlertRed else DarkBorder,
                                RoundedCornerShape(6.dp)
                            )
                            .padding(10.dp)
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Box(
                                        modifier = Modifier
                                            .clip(RoundedCornerShape(3.dp))
                                            .background(
                                                if (isSos) AlertRedSurface else if (isSafe) SafeGreenSurface else ActionSlate
                                            )
                                            .padding(horizontal = 4.dp, vertical = 2.dp)
                                    ) {
                                        Text(
                                            text = if (isSos) "SOS" else if (isSafe) "SAFE" else "REPORT",
                                            fontSize = 9.sp,
                                            fontWeight = FontWeight.Black,
                                            color = if (isSos) AlertRed else if (isSafe) SafeGreen else TextPrimary
                                        )
                                    }

                                    Text(
                                        text = "${packet.senderName} (Age ${packet.senderAge}, ${packet.senderNationality})",
                                        fontSize = 12.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = Color.White
                                    )
                                }

                                Text(
                                    text = "Hop ${packet.hopCount}/5",
                                    fontSize = 10.sp,
                                    color = TextMuted
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
                                    text = "Location: ${String.format(java.util.Locale.US, "%.4f, %.4f", packet.lat, packet.lng)}",
                                    fontSize = 10.sp,
                                    color = TextMuted
                                )
                                Text(
                                    text = if (packet.isRelayed) "Relayed Swarm" else "Direct Broadcast",
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = if (packet.isRelayed) SafeGreen else TextSecondary
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
