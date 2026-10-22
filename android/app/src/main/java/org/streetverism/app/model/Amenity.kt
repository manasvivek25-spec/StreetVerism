package org.streetverism.app.model

import kotlin.math.*

enum class AmenityType(val label: String, val icon: String, val markerColorHex: String) {
    HOSPITAL("Hospital / Trauma", "🏥", "#EF4444"),
    PHARMACY("Pharmacy / Medicals", "💊", "#10B981"),
    FOOD_WATER("Food & Clean Water", "🍲", "#3B82F6"),
    FIRST_AID("First Aid Station", "🩹", "#F59E0B"),
    SHELTER("Safe Relief Shelter", "🛡️", "#8B5CF6")
}

data class Amenity(
    val id: String,
    val name: String,
    val type: AmenityType,
    val lat: Double,
    val lng: Double,
    val address: String,
    val contactNumber: String,
    val is24x7: Boolean,
    val suppliesAvailable: List<String>,
    val capacity: String,
    val verifiedOffline: Boolean = true
) {
    /**
     * Compute Great Circle Haversine distance in meters to user coordinates.
     */
    fun distanceMetersTo(userLat: Double, userLng: Double): Double {
        val r = 6371000.0 // Earth radius in meters
        val dLat = Math.toRadians(lat - userLat)
        val dLng = Math.toRadians(lng - userLng)
        val a = sin(dLat / 2).pow(2) +
                cos(Math.toRadians(userLat)) * cos(Math.toRadians(lat)) *
                sin(dLng / 2).pow(2)
        val c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return r * c
    }

    /**
     * Compute initial forward azimuth bearing in degrees [0, 360) from user to amenity.
     */
    fun bearingFrom(userLat: Double, userLng: Double): Double {
        val phi1 = Math.toRadians(userLat)
        val phi2 = Math.toRadians(lat)
        val dLambda = Math.toRadians(lng - userLng)

        val y = sin(dLambda) * cos(phi2)
        val x = cos(phi1) * sin(phi2) - sin(phi1) * cos(phi2) * cos(dLambda)
        val theta = atan2(y, x)
        return (Math.toDegrees(theta) + 360.0) % 360.0
    }

    /**
     * 8-point compass sector representation (e.g. "NE", "SW", "N").
     */
    fun compassDirectionFrom(userLat: Double, userLng: Double): String {
        val bearing = bearingFrom(userLat, userLng)
        val sectors = arrayOf("N", "NE", "E", "SE", "S", "SW", "W", "NW")
        val index = (((bearing + 22.5) / 45.0).toInt()) % 8
        return sectors[index]
    }
}
