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
import org.streetverism.app.model.CrisisPrecaution
import org.streetverism.app.model.FirstAidGuide
import org.streetverism.app.ui.theme.*

@Composable
fun SafetyGuideScreen(
    precautions: List<CrisisPrecaution>,
    firstAidGuides: List<FirstAidGuide>
) {
    var activeTab by remember { mutableStateOf(0) } // 0 = Precautions, 1 = First Aid

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
                text = "DISASTER PROTOCOLS & FIRST AID",
                fontSize = 18.sp,
                fontWeight = FontWeight.Black,
                color = Color.White,
                letterSpacing = 0.5.sp
            )
            Text(
                text = "100% offline emergency procedures, hazard precautions, and step-by-step triage.",
                fontSize = 12.sp,
                color = TextSecondary
            )
        }

        // Two Segmented Tabs
        TabRow(
            selectedTabIndex = activeTab,
            containerColor = DarkSurfaceElevated,
            contentColor = Color.White
        ) {
            Tab(
                selected = activeTab == 0,
                onClick = { activeTab = 0 },
                text = { Text("WEATHER PRECAUTIONS", fontWeight = FontWeight.Bold, fontSize = 12.sp) }
            )
            Tab(
                selected = activeTab == 1,
                onClick = { activeTab = 1 },
                text = { Text("FIRST AID PROTOCOLS", fontWeight = FontWeight.Bold, fontSize = 12.sp) }
            )
        }

        // Tab Content
        if (activeTab == 0) {
            // Precautions List
            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                items(precautions) { prec ->
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .background(DarkSurface)
                            .border(1.dp, DarkBorder, RoundedCornerShape(8.dp))
                            .padding(14.dp)
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Box(
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(4.dp))
                                        .background(ActionSlate)
                                        .padding(horizontal = 6.dp, vertical = 3.dp)
                                ) {
                                    Text("PROTOCOL", fontSize = 9.sp, fontWeight = FontWeight.Black, color = Color.White)
                                }

                                Column {
                                    Text(
                                        text = prec.crisisType.uppercase(),
                                        fontSize = 15.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = Color.White
                                    )
                                    Text(
                                        text = prec.summary,
                                        fontSize = 12.sp,
                                        color = TextSecondary
                                    )
                                }
                            }

                            // DO THIS Box
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(6.dp))
                                    .background(SafeGreenSurface)
                                    .border(1.dp, SafeGreen, RoundedCornerShape(6.dp))
                                    .padding(10.dp)
                            ) {
                                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Text(
                                        text = "CRITICAL ACTIONS (DO THIS):",
                                        fontSize = 11.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = SafeGreen
                                    )
                                    prec.dos.forEach { item ->
                                        Text(text = "• $item", fontSize = 12.sp, color = TextPrimary, lineHeight = 16.sp)
                                    }
                                }
                            }

                            // DO NOT DO THIS Box
                            Box(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(6.dp))
                                    .background(AlertRedSurface)
                                    .border(1.dp, AlertRed, RoundedCornerShape(6.dp))
                                    .padding(10.dp)
                            ) {
                                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Text(
                                        text = "PROHIBITED ACTIONS (NEVER DO THIS):",
                                        fontSize = 11.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = AlertRed
                                    )
                                    prec.donts.forEach { item ->
                                        Text(text = "• $item", fontSize = 12.sp, color = TextPrimary, lineHeight = 16.sp)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        } else {
            // First Aid Procedures List
            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                items(firstAidGuides) { guide ->
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .background(DarkSurface)
                            .border(1.dp, DarkBorder, RoundedCornerShape(8.dp))
                            .padding(14.dp)
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.Top
                            ) {
                                Column {
                                    Text(
                                        text = guide.condition.uppercase(),
                                        fontSize = 15.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = Color.White
                                    )
                                    Text(
                                        text = "PRIORITY: ${guide.urgency.uppercase()}",
                                        fontSize = 11.sp,
                                        fontWeight = FontWeight.Black,
                                        color = AlertRed
                                    )
                                }
                            }

                            // Step-by-Step Triage
                            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                guide.steps.forEachIndexed { index, step ->
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                                        verticalAlignment = Alignment.Top
                                    ) {
                                        Box(
                                            modifier = Modifier
                                                .size(20.dp)
                                                .clip(RoundedCornerShape(4.dp))
                                                .background(ActionSlate),
                                            contentAlignment = Alignment.Center
                                        ) {
                                            Text(
                                                text = "${index + 1}",
                                                fontSize = 11.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = Color.White
                                            )
                                        }

                                        Text(
                                            text = step,
                                            fontSize = 13.sp,
                                            color = TextPrimary,
                                            lineHeight = 18.sp,
                                            modifier = Modifier.weight(1f)
                                        )
                                    }
                                }
                            }

                            // Critical Warnings Box
                            if (guide.warnings.isNotEmpty()) {
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clip(RoundedCornerShape(6.dp))
                                        .background(AlertRedSurface)
                                        .border(1.dp, AlertRed, RoundedCornerShape(6.dp))
                                        .padding(10.dp)
                                ) {
                                    Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                        Text(
                                            text = "LIFE-CRITICAL WARNINGS:",
                                            fontSize = 11.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = AlertRed
                                        )
                                        guide.warnings.forEach { warn ->
                                            Text(text = "• $warn", fontSize = 12.sp, color = Color.White)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
