package org.streetverism.app.model

/**
 * Minimal crisis user profile.
 * Only collects Name, Age, Language, and Nationality.
 *
 * Age is used locally to:
 * 1. Weight crowd report credibility (e.g., verifying observations).
 * 2. Prioritize search-and-rescue dispatch for vulnerable demographics (children <14 and seniors >65).
 */
data class UserProfile(
    val name: String,
    val age: Int,
    val language: String,
    val nationality: String,
    val registeredAtEpochMs: Long = System.currentTimeMillis()
) {
    /**
     * Compute reporter credibility multiplier for Bayesian trust fusion.
     * Children and adolescents require higher corroboration thresholds to prevent panic rumor inflation.
     * Adults carry standard 1.0x calibration weight.
     */
    fun calculateCredibilityFactor(): Float {
        return when {
            age < 14 -> 0.50f   // Child observer: cautious weighting, priority for rescue
            age in 14..17 -> 0.75f // Youth observer
            age in 18..64 -> 1.00f // Standard adult observer
            else -> 0.90f          // Senior observer: high credibility with urgent medical vulnerability
        }
    }

    /**
     * Returns true if user falls in humanitarian vulnerable demographic.
     */
    fun isVulnerable(): Boolean = age < 14 || age >= 65

    fun vulnerabilityTier(): String {
        return when {
            age < 14 -> "CHILD · HIGH RESCUE PRIORITY"
            age in 14..17 -> "YOUTH"
            age in 18..64 -> "ADULT"
            else -> "SENIOR CITIZEN · PRIORITY MEDICAL TRIAGE"
        }
    }

    fun getLanguageDisplayName(): String {
        return when (language.lowercase()) {
            "ta" -> "தமிழ் (Tamil)"
            "hi" -> "हिन्दी (Hindi)"
            "de" -> "Deutsch (German)"
            "fr" -> "Français (French)"
            "ja" -> "日本語 (Japanese)"
            "es" -> "Español (Spanish)"
            else -> "English"
        }
    }
}
