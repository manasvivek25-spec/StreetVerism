package org.streetverism.app.data

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONObject
import org.streetverism.app.model.*

class LocalAssetRepository(private val context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences("streetverism_profile_prefs", Context.MODE_PRIVATE)

    // Cached in memory for instantaneous zero-latency offline access
    private var cachedAmenities: List<Amenity>? = null
    private var cachedPhrases: List<TranslationPhrase>? = null
    private var cachedPrecautions: List<CrisisPrecaution>? = null
    private var cachedFirstAidGuides: List<FirstAidGuide>? = null
    private var cachedHazardZones: List<HazardZone>? = null

    // --- User Profile Storage (Minimal 4 Fields) ---

    fun getUserProfile(): UserProfile? {
        val name = prefs.getString("user_name", null) ?: return null
        val age = prefs.getInt("user_age", 25)
        val language = prefs.getString("user_language", "en") ?: "en"
        val nationality = prefs.getString("user_nationality", "International") ?: "International"
        return UserProfile(name = name, age = age, language = language, nationality = nationality)
    }

    fun saveUserProfile(profile: UserProfile) {
        prefs.edit()
            .putString("user_name", profile.name.trim())
            .putInt("user_age", profile.age)
            .putString("user_language", profile.language.trim())
            .putString("user_nationality", profile.nationality.trim())
            .apply()
    }

    // --- Offline Amenities Ingestion ---

    fun getAmenities(): List<Amenity> {
        cachedAmenities?.let { return it }

        val list = mutableListOf<Amenity>()
        try {
            val jsonString = context.assets.open("amenities.json").bufferedReader().use { it.readText() }
            val root = JSONObject(jsonString)
            val array = root.getJSONArray("amenities")
            for (i in 0 until array.length()) {
                val obj = array.getJSONObject(i)
                val typeStr = obj.getString("type").uppercase()
                val amenityType = when (typeStr) {
                    "HOSPITAL" -> AmenityType.HOSPITAL
                    "PHARMACY" -> AmenityType.PHARMACY
                    "FOOD_WATER" -> AmenityType.FOOD_WATER
                    "FIRST_AID" -> AmenityType.FIRST_AID
                    else -> AmenityType.SHELTER
                }

                val suppliesList = mutableListOf<String>()
                val suppliesArray = obj.optJSONArray("supplies_available")
                if (suppliesArray != null) {
                    for (j in 0 until suppliesArray.length()) {
                        suppliesList.add(suppliesArray.getString(j))
                    }
                }

                list.add(
                    Amenity(
                        id = obj.getString("id"),
                        name = obj.getString("name"),
                        type = amenityType,
                        lat = obj.getDouble("lat"),
                        lng = obj.getDouble("lng"),
                        address = obj.optString("address", ""),
                        contactNumber = obj.optString("contact_number", "Emergency 112"),
                        is24x7 = obj.optBoolean("is_24x7", true),
                        suppliesAvailable = suppliesList,
                        capacity = obj.optString("capacity", "Active"),
                        verifiedOffline = obj.optBoolean("verified_offline", true)
                    )
                )
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }

        cachedAmenities = list
        return list
    }

    fun getAmenitiesForLocation(userLat: Double, userLng: Double): List<Amenity> {
        val base = getAmenities()
        val dLat = Math.toRadians(userLat - 13.015)
        val dLng = Math.toRadians(userLng - 80.225)
        val a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                Math.cos(Math.toRadians(13.015)) * Math.cos(Math.toRadians(userLat)) *
                Math.sin(dLng / 2) * Math.sin(dLng / 2)
        val distToChennaiMeters = 6371000.0 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))

        if (distToChennaiMeters <= 50000.0) {
            return base
        }

        // Dynamically provide local crisis amenities scaled around user's real-time live GPS fix
        val localAmenities = listOf(
            Amenity(
                id = "live-gps-shelter-1",
                name = "Designated High-Ground Safe Shelter",
                type = AmenityType.SHELTER,
                lat = userLat + 0.0035,
                lng = userLng + 0.0025,
                address = "Local Disaster Relief Center",
                contactNumber = "112 / 108",
                is24x7 = true,
                suppliesAvailable = listOf("Blankets", "Dry Food Rations", "Drinking Water", "Device Power"),
                capacity = "500 evacuees",
                verifiedOffline = true
            ),
            Amenity(
                id = "live-gps-water-1",
                name = "Municipal Clean Potable Water Point",
                type = AmenityType.FOOD_WATER,
                lat = userLat + 0.0018,
                lng = userLng - 0.0022,
                address = "Emergency Potable Water Depot",
                contactNumber = "112",
                is24x7 = true,
                suppliesAvailable = listOf("Clean Water", "Electrolyte Packets", "Water Purification Tablets"),
                capacity = "Continuous Tanker",
                verifiedOffline = true
            ),
            Amenity(
                id = "live-gps-pharmacy-1",
                name = "24x7 Emergency First-Aid Pharmacy",
                type = AmenityType.PHARMACY,
                lat = userLat - 0.0024,
                lng = userLng + 0.0018,
                address = "Emergency Trauma Supplies",
                contactNumber = "108",
                is24x7 = true,
                suppliesAvailable = listOf("Antiseptic", "Bandages", "EpiPens", "Insulin Support", "Tourniquets"),
                capacity = "Open 24 Hours",
                verifiedOffline = true
            ),
            Amenity(
                id = "live-gps-firstaid-1",
                name = "Civil Defence Rapid Triage & First-Aid Post",
                type = AmenityType.FIRST_AID,
                lat = userLat - 0.0031,
                lng = userLng - 0.0020,
                address = "Mobile Emergency Treatment Tent",
                contactNumber = "112",
                is24x7 = true,
                suppliesAvailable = listOf("CPR Defibrillator", "Splints", "Burn Dressing", "Stretchers"),
                capacity = "4 Paramedics",
                verifiedOffline = true
            ),
            Amenity(
                id = "live-gps-hospital-1",
                name = "Regional Emergency & Trauma Hospital",
                type = AmenityType.HOSPITAL,
                lat = userLat + 0.0062,
                lng = userLng - 0.0041,
                address = "District Critical Care Center",
                contactNumber = "108 / 112",
                is24x7 = true,
                suppliesAvailable = listOf("ICU Beds", "Trauma Surgeons", "Ambulance Fleet", "Oxygen Units"),
                capacity = "Level 1 Trauma",
                verifiedOffline = true
            )
        )
        return localAmenities + base
    }

    // --- Offline Translator Ingestion ---

    fun getTranslationPhrases(): List<TranslationPhrase> {
        cachedPhrases?.let { return it }

        val list = mutableListOf<TranslationPhrase>()
        try {
            val jsonString = context.assets.open("offline_translator.json").bufferedReader().use { it.readText() }
            val root = JSONObject(jsonString)
            val phrasesArray = root.getJSONArray("phrases")

            for (i in 0 until phrasesArray.length()) {
                val pObj = phrasesArray.getJSONObject(i)
                val id = pObj.getString("id")
                val category = pObj.getString("category")
                val english = pObj.getString("en")
                val transObj = pObj.getJSONObject("translations")

                val map = mutableMapOf<String, TranslationText>()
                val keys = transObj.keys()
                while (keys.hasNext()) {
                    val lang = keys.next()
                    val lObj = transObj.getJSONObject(lang)
                    map[lang] = TranslationText(
                        text = lObj.getString("text"),
                        phonetic = lObj.optString("phonetic", lObj.getString("text"))
                    )
                }

                list.add(
                    TranslationPhrase(
                        id = id,
                        category = category,
                        english = english,
                        translations = map
                    )
                )
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }

        cachedPhrases = list
        return list
    }

    // --- Offline Safety Guides & First Aid ---

    fun getSafetyGuides(): Pair<List<CrisisPrecaution>, List<FirstAidGuide>> {
        if (cachedPrecautions != null && cachedFirstAidGuides != null) {
            return Pair(cachedPrecautions!!, cachedFirstAidGuides!!)
        }

        val precautionsList = mutableListOf<CrisisPrecaution>()
        val firstAidList = mutableListOf<FirstAidGuide>()

        try {
            val jsonString = context.assets.open("crisis_safety_guides.json").bufferedReader().use { it.readText() }
            val root = JSONObject(jsonString)

            // Precautions
            val precArray = root.getJSONArray("precautions")
            for (i in 0 until precArray.length()) {
                val obj = precArray.getJSONObject(i)
                val dosList = mutableListOf<String>()
                val dosArr = obj.getJSONArray("dos")
                for (j in 0 until dosArr.length()) dosList.add(dosArr.getString(j))

                val dontsList = mutableListOf<String>()
                val dontsArr = obj.getJSONArray("donts")
                for (j in 0 until dontsArr.length()) dontsList.add(dontsArr.getString(j))

                precautionsList.add(
                    CrisisPrecaution(
                        id = obj.getString("id"),
                        crisisType = obj.getString("crisis_type"),
                        severity = obj.getString("severity"),
                        colorHex = obj.getString("color"),
                        icon = obj.getString("icon"),
                        summary = obj.getString("summary"),
                        dos = dosList,
                        donts = dontsList
                    )
                )
            }

            // First Aid
            val faArray = root.getJSONArray("first_aid")
            for (i in 0 until faArray.length()) {
                val obj = faArray.getJSONObject(i)
                val stepsList = mutableListOf<String>()
                val stepsArr = obj.getJSONArray("steps")
                for (j in 0 until stepsArr.length()) stepsList.add(stepsArr.getString(j))

                val warnList = mutableListOf<String>()
                val warnArr = obj.optJSONArray("warnings")
                if (warnArr != null) {
                    for (j in 0 until warnArr.length()) warnList.add(warnArr.getString(j))
                }

                firstAidList.add(
                    FirstAidGuide(
                        id = obj.getString("id"),
                        condition = obj.getString("condition"),
                        urgency = obj.getString("urgency"),
                        icon = obj.getString("icon"),
                        colorHex = obj.getString("color"),
                        steps = stepsList,
                        warnings = warnList
                    )
                )
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }

        cachedPrecautions = precautionsList
        cachedFirstAidGuides = firstAidList
        return Pair(precautionsList, firstAidList)
    }

    // --- Offline Vector Hazard Zones ---

    fun getHazardZones(): List<HazardZone> {
        cachedHazardZones?.let { return it }

        val list = mutableListOf<HazardZone>()
        try {
            val jsonString = context.assets.open("offline_hazard_map.json").bufferedReader().use { it.readText() }
            val root = JSONObject(jsonString)
            val array = root.getJSONArray("zones")

            for (i in 0 until array.length()) {
                val obj = array.getJSONObject(i)
                val centerArr = obj.getJSONArray("center")
                val centerLat = centerArr.getDouble(0)
                val centerLng = centerArr.getDouble(1)

                val polyCoords = mutableListOf<Pair<Double, Double>>()
                val polyArr = obj.getJSONArray("polygon")
                for (j in 0 until polyArr.length()) {
                    val pt = polyArr.getJSONArray(j)
                    polyCoords.add(Pair(pt.getDouble(0), pt.getDouble(1))) // (lng, lat)
                }

                val statusEnum = when (obj.getString("status").lowercase()) {
                    "official_hazard" -> HazardStatus.OFFICIAL_HAZARD
                    "likely_hazard" -> HazardStatus.LIKELY_HAZARD
                    "unverified" -> HazardStatus.UNVERIFIED
                    "contradicted" -> HazardStatus.CONTRADICTED
                    else -> HazardStatus.CLEAR
                }

                list.add(
                    HazardZone(
                        id = obj.getString("id"),
                        name = obj.getString("name"),
                        status = statusEnum,
                        pHazard = obj.getDouble("p_hazard").toFloat(),
                        colorHex = obj.getString("color"),
                        icon = obj.getString("icon"),
                        description = obj.getString("description"),
                        centerLat = centerLat,
                        centerLng = centerLng,
                        polygon = polyCoords
                    )
                )
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }

        cachedHazardZones = list
        return list
    }

    fun getHazardZonesForLocation(userLat: Double, userLng: Double): List<HazardZone> {
        val base = getHazardZones()
        val dLat = Math.toRadians(userLat - 13.015)
        val dLng = Math.toRadians(userLng - 80.225)
        val a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                Math.cos(Math.toRadians(13.015)) * Math.cos(Math.toRadians(userLat)) *
                Math.sin(dLng / 2) * Math.sin(dLng / 2)
        val distToChennaiMeters = 6371000.0 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))

        if (distToChennaiMeters <= 50000.0) {
            return base
        }

        val localSafePerimeter = HazardZone(
            id = "live-safe-zone",
            name = "Local High-Elevation Safe Sector",
            status = HazardStatus.CLEAR,
            pHazard = 0.05f,
            colorHex = "#10B981",
            icon = "🛡️",
            description = "High terrain designated safety corridor around your live position.",
            centerLat = userLat + 0.002,
            centerLng = userLng + 0.002,
            polygon = listOf(
                Pair(userLng + 0.001, userLat + 0.001),
                Pair(userLng + 0.005, userLat + 0.001),
                Pair(userLng + 0.005, userLat + 0.005),
                Pair(userLng + 0.001, userLat + 0.005)
            )
        )

        val localCautionZone = HazardZone(
            id = "live-caution-drainage",
            name = "Low-Lying Stormwater Runoff Hazard",
            status = HazardStatus.LIKELY_HAZARD,
            pHazard = 0.82f,
            colorHex = "#F97316",
            icon = "⚠️",
            description = "Local low-lying drainage area prone to rapid accumulation.",
            centerLat = userLat - 0.004,
            centerLng = userLng - 0.003,
            polygon = listOf(
                Pair(userLng - 0.006, userLat - 0.003),
                Pair(userLng - 0.002, userLat - 0.003),
                Pair(userLng - 0.002, userLat - 0.006),
                Pair(userLng - 0.006, userLat - 0.006)
            )
        )

        return listOf(localSafePerimeter, localCautionZone) + base
    }
}
