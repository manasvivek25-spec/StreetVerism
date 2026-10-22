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
}
