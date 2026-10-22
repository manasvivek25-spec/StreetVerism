package org.streetverism.app.model

data class TranslationText(
    val text: String,
    val phonetic: String
)

data class TranslationPhrase(
    val id: String,
    val category: String,
    val english: String,
    val translations: Map<String, TranslationText>
) {
    /**
     * Resolve phrase for a target language code with English fallback.
     */
    fun resolve(langCode: String): TranslationText {
        val target = translations[langCode.lowercase()]
        if (target != null) return target

        // Fallback for English
        return TranslationText(text = english, phonetic = english)
    }
}

data class CrisisPrecaution(
    val id: String,
    val crisisType: String,
    val severity: String,
    val colorHex: String,
    val icon: String,
    val summary: String,
    val dos: List<String>,
    val donts: List<String>
)

data class FirstAidGuide(
    val id: String,
    val condition: String,
    val urgency: String,
    val icon: String,
    val colorHex: String,
    val steps: List<String>,
    val warnings: List<String>
)

enum class HazardStatus(val label: String, val colorHex: String, val icon: String) {
    OFFICIAL_HAZARD("OFFICIAL HAZARD", "#EF4444", "🚨"),
    LIKELY_HAZARD("LIKELY HAZARD", "#F97316", "⚠️"),
    UNVERIFIED("UNVERIFIED CAUTION", "#EAB308", "❓"),
    CONTRADICTED("CONTRADICTED", "#818CF8", "ℹ️"),
    CLEAR("CLEAR / SAFE", "#10B981", "🛡️")
}

data class HazardZone(
    val id: String,
    val name: String,
    val status: HazardStatus,
    val pHazard: Float,
    val colorHex: String,
    val icon: String,
    val description: String,
    val centerLat: Double,
    val centerLng: Double,
    val polygon: List<Pair<Double, Double>> // List of (lng, lat) pairs
)
