package org.streetverism.app.trust

import org.streetverism.app.model.HazardStatus
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.min

data class LocalReport(
    val id: String,
    val deviceId: String,
    val reporterAge: Int = 30,
    val reporterName: String = "Citizen",
    val claim: String, // "flooded", "blocked", "safe"
    val timestampSeconds: Long,
    val text: String? = null
)

data class CellAssessment(
    val status: HazardStatus,
    val pHazard: Float,
    val priorProbability: Float,
    val crowdLogitRaw: Float,
    val crowdLogitClamped: Float,
    val corroboratedClustersCount: Int,
    val dominantEvidenceSummary: String
)

/**
 * Pure Kotlin On-Device Bayesian Trust Engine.
 * Runs 100% locally with zero internet connectivity.
 * Implements calibrated log-odds evidence fusion, temporal decay, and age-based credibility weighting.
 */
object BayesianTrustEngine {
    const val PRIOR_INTERCEPT = -4.0f
    const val BETA_RAIN_3H = 0.04f
    const val BETA_RAIN_24H = 0.01f
    const val BETA_FLOOD_PRONE = 1.50f

    const val MAX_RAIN_3H = 150.0f
    const val MAX_RAIN_24H = 400.0f

    // Calibrated Log-Likelihood Ratios (Sensitivity 0.70, Specificity 0.85)
    const val LLR_HAZARD_DEFAULT = 1.540445f
    const val LLR_SAFE_DEFAULT = -1.041454f

    // Temporal Decay: Exact 2-Hour Half-Life
    const val HALF_LIFE_SECONDS = 7200.0
    private val DECAY_LAMBDA = ln(2.0) / HALF_LIFE_SECONDS

    // Hard Mathematical Clamping: Prevents Mob Panic Inflation
    const val CROWD_LOGIT_MIN = -3.0f
    const val CROWD_LOGIT_MAX = 3.0f

    /**
     * Compute baseline prior logit odds from rainfall and topographical flood vulnerability.
     */
    fun computePriorLogit(
        rainMm3h: Float,
        rainMm24h: Float,
        floodProne: Boolean
    ): Float {
        val cappedRain3h = min(max(0.0f, rainMm3h), MAX_RAIN_3H)
        val cappedRain24h = min(max(0.0f, rainMm24h), MAX_RAIN_24H)
        val terrainBonus = if (floodProne) BETA_FLOOD_PRONE else 0.0f

        return PRIOR_INTERCEPT +
                (BETA_RAIN_3H * cappedRain3h) +
                (BETA_RAIN_24H * cappedRain24h) +
                terrainBonus
    }

    /**
     * Logistic sigmoid mapping logit to probability [0.0, 1.0].
     */
    fun sigmoid(logit: Float): Float {
        return 1.0f / (1.0f + exp(-logit))
    }

    /**
     * Assess cell hazard level on-device.
     */
    fun assess(
        currentTimestampSeconds: Long,
        rainMm3h: Float = 0.0f,
        rainMm24h: Float = 0.0f,
        floodProne: Boolean = false,
        reports: List<LocalReport> = emptyList(),
        hasOfficialHazardAlert: Boolean = false,
        hasOfficialAllClearAlert: Boolean = false
    ): CellAssessment {
        // 1. Authoritative Override takes absolute priority
        if (hasOfficialHazardAlert) {
            return CellAssessment(
                status = HazardStatus.OFFICIAL_HAZARD,
                pHazard = 0.99f,
                priorProbability = 0.99f,
                crowdLogitRaw = 0.0f,
                crowdLogitClamped = 0.0f,
                corroboratedClustersCount = 0,
                dominantEvidenceSummary = "Official emergency alert issued by disaster management authority."
            )
        }

        // 2. Prior Logit calculation
        val priorLogit = computePriorLogit(rainMm3h, rainMm24h, floodProne)
        val priorProbability = sigmoid(priorLogit)

        // 3. Process crowd reports with Age-Credibility weighting and Temporal Decay
        var totalCrowdLogit = 0.0f
        var corroboratedCount = 0

        val activeReports = reports.filter { (currentTimestampSeconds - it.timestampSeconds) in 0..21600 } // Within 6 hours

        for (report in activeReports) {
            val ageElapsedSeconds = max(0L, currentTimestampSeconds - report.timestampSeconds)
            val decayFactor = exp(-DECAY_LAMBDA * ageElapsedSeconds).toFloat()

            // Age-based credibility multiplier:
            // Under 14: 0.50x (cautious, requires adult corroboration)
            // 14-17: 0.75x
            // 18-64: 1.00x
            // 65+: 0.90x
            val ageMultiplier = when {
                report.reporterAge < 14 -> 0.50f
                report.reporterAge in 14..17 -> 0.75f
                report.reporterAge in 18..64 -> 1.00f
                else -> 0.90f
            }

            val baseLlr = if (report.claim == "safe") LLR_SAFE_DEFAULT else LLR_HAZARD_DEFAULT
            val weightedLlr = baseLlr * ageMultiplier * decayFactor
            totalCrowdLogit += weightedLlr

            // Corroborated within 4 hours
            if (ageElapsedSeconds <= 14400 && report.claim != "safe") {
                corroboratedCount++
            }
        }

        // 4. Mathematical Clamping
        val crowdLogitClamped = min(max(totalCrowdLogit, CROWD_LOGIT_MIN), CROWD_LOGIT_MAX)

        // 5. Posterior Probability
        val posteriorLogit = priorLogit + crowdLogitClamped
        val posteriorProbability = sigmoid(posteriorLogit)

        // 6. Classification Decision
        val status = when {
            hasOfficialAllClearAlert && activeReports.any { it.claim != "safe" } -> HazardStatus.CONTRADICTED
            hasOfficialAllClearAlert -> HazardStatus.CLEAR
            posteriorProbability >= 0.80f && corroboratedCount >= 2 -> HazardStatus.LIKELY_HAZARD
            posteriorProbability >= 0.50f || activeReports.any { it.claim != "safe" } -> HazardStatus.UNVERIFIED
            else -> HazardStatus.CLEAR
        }

        val summary = when (status) {
            HazardStatus.OFFICIAL_HAZARD -> "Official Civil Defence Warning."
            HazardStatus.LIKELY_HAZARD -> "High probability synthesized from corroborated observations (P=${(posteriorProbability * 100).toInt()}%)."
            HazardStatus.UNVERIFIED -> "Unverified social reports detected. Corroboration in progress; wait for official updates."
            HazardStatus.CONTRADICTED -> "Prior social reports contradicted by official survey."
            HazardStatus.CLEAR -> "No active hazard indicators detected in this area. Conditions normal."
        }

        return CellAssessment(
            status = status,
            pHazard = posteriorProbability,
            priorProbability = priorProbability,
            crowdLogitRaw = totalCrowdLogit,
            crowdLogitClamped = crowdLogitClamped,
            corroboratedClustersCount = corroboratedCount,
            dominantEvidenceSummary = summary
        )
    }
}
