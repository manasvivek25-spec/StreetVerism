package org.streetverism.app.location

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.Looper
import android.provider.Settings
import androidx.core.content.ContextCompat
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class LiveGpsState(
    val latitude: Double = 13.0150,
    val longitude: Double = 80.2250,
    val accuracy: Float = 0f,
    val altitude: Double = 0.0,
    val speed: Float = 0f,
    val bearing: Float = 0f,
    val isLive: Boolean = false,
    val isGpsEnabled: Boolean = false,
    val hasPermission: Boolean = false,
    val provider: String = "None",
    val statusMessage: String = "Initializing GPS..."
)

class GpsLocationManager(private val context: Context) : LocationListener {

    private val locationManager = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager

    private val _gpsState = MutableStateFlow(LiveGpsState())
    val gpsState: StateFlow<LiveGpsState> = _gpsState.asStateFlow()

    private var isListening = false

    fun checkPermissions(): Boolean {
        val finePerm = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        val coarsePerm = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_COARSE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        val granted = finePerm || coarsePerm
        _gpsState.value = _gpsState.value.copy(hasPermission = granted)
        return granted
    }

    fun isGpsHardwareEnabled(): Boolean {
        return try {
            locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER) ||
                    locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
        } catch (e: Exception) {
            false
        }
    }

    @SuppressLint("MissingPermission")
    fun startLocationUpdates() {
        if (!checkPermissions()) {
            _gpsState.value = _gpsState.value.copy(
                statusMessage = "Location permission required for live GPS"
            )
            return
        }

        val gpsEnabled = isGpsHardwareEnabled()
        _gpsState.value = _gpsState.value.copy(isGpsEnabled = gpsEnabled)

        if (!gpsEnabled) {
            _gpsState.value = _gpsState.value.copy(
                statusMessage = "Device GPS is disabled. Please turn on Location in Settings."
            )
        }

        // 1. Immediately read last known location for zero-latency initial position
        var lastLocation: Location? = null
        try {
            if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                lastLocation = locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER)
            }
            if (lastLocation == null && locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                lastLocation = locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
            }
            if (lastLocation == null && locationManager.isProviderEnabled(LocationManager.PASSIVE_PROVIDER)) {
                lastLocation = locationManager.getLastKnownLocation(LocationManager.PASSIVE_PROVIDER)
            }
        } catch (e: Exception) {
            // Permission or security exception fallback
        }

        if (lastLocation != null) {
            updateFromLocation(lastLocation, isRealtime = true, note = "Cached Satellite Fix")
        }

        if (isListening) return

        try {
            // 2. Request fast continuous offline GPS updates (interval 1000ms, distance 0.5m)
            if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                locationManager.requestLocationUpdates(
                    LocationManager.GPS_PROVIDER,
                    1000L,
                    0.5f,
                    this,
                    Looper.getMainLooper()
                )
                isListening = true
                _gpsState.value = _gpsState.value.copy(
                    statusMessage = "Acquiring satellite lock..."
                )
            }

            // Also register network / tower provider if available for instant indoor fixes
            if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                locationManager.requestLocationUpdates(
                    LocationManager.NETWORK_PROVIDER,
                    2000L,
                    1.0f,
                    this,
                    Looper.getMainLooper()
                )
                isListening = true
            }
        } catch (e: Exception) {
            _gpsState.value = _gpsState.value.copy(
                statusMessage = "GPS error: ${e.localizedMessage}"
            )
        }
    }

    fun stopLocationUpdates() {
        if (!isListening) return
        try {
            locationManager.removeUpdates(this)
            isListening = false
        } catch (e: Exception) {
            // Ignored
        }
    }

    override fun onLocationChanged(location: Location) {
        updateFromLocation(location, isRealtime = true, note = "Live Satellite Fix")
    }

    private fun updateFromLocation(location: Location, isRealtime: Boolean, note: String) {
        _gpsState.value = LiveGpsState(
            latitude = location.latitude,
            longitude = location.longitude,
            accuracy = location.accuracy,
            altitude = location.altitude,
            speed = location.speed,
            bearing = location.bearing,
            isLive = isRealtime,
            isGpsEnabled = true,
            hasPermission = true,
            provider = location.provider ?: "GPS",
            statusMessage = "$note (±${location.accuracy.toInt()}m)"
        )
    }

    override fun onProviderEnabled(provider: String) {
        _gpsState.value = _gpsState.value.copy(
            isGpsEnabled = true,
            statusMessage = "Provider $provider enabled"
        )
    }

    override fun onProviderDisabled(provider: String) {
        _gpsState.value = _gpsState.value.copy(
            isGpsEnabled = isGpsHardwareEnabled(),
            statusMessage = "Provider $provider disabled"
        )
    }

    @Deprecated("Deprecated in Java")
    override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) {
        // Required for backward compatibility on some Android versions
    }

    fun openLocationSettings() {
        try {
            val intent = Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            // Fallback
        }
    }
}
