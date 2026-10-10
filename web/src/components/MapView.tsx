import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Shelter } from '../api/types';

interface MapViewProps {
  userLocation: { lat: number; lng: number } | null;
  shelters: Shelter[];
  cell: string;
  statusLabel: string;
  isReplay: boolean;
  isFallback: boolean;
  backendMode?: string;
}

const userIcon = L.divIcon({
  className: 'custom-user-marker',
  html: '<div style="background: #d7f34a; border: 3px solid #071827; width: 22px; height: 22px; border-radius: 50%; box-shadow: 0 0 12px rgba(215, 243, 74, 0.8); display: flex; align-items: center; justify-content: center; font-size: 10px;">U</div>',
  iconSize: [22, 22],
  iconAnchor: [11, 11],
});

const shelterIcon = L.divIcon({
  className: 'custom-shelter-marker',
  html: '<div style="background: #0b1f32; border: 2px solid #22c55e; color: #4ade80; padding: 3px 6px; border-radius: 6px; font-size: 12px; font-weight: 700; white-space: nowrap; box-shadow: 0 2px 8px rgba(0,0,0,0.5);">Shelter</div>',
  iconSize: [60, 24],
  iconAnchor: [30, 12],
});

export const MapView: React.FC<MapViewProps> = ({
  userLocation,
  shelters,
  cell,
  statusLabel,
  isReplay,
  isFallback,
  backendMode,
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [13.0827, 80.2707],
        zoom: 12,
        zoomControl: true,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      markersLayerRef.current = L.layerGroup().addTo(map);
      mapInstanceRef.current = map;
    }

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
        markersLayerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    const map = mapInstanceRef.current;
    const markersLayer = markersLayerRef.current;
    if (!map || !markersLayer) return;

    markersLayer.clearLayers();

    if (!userLocation) {
      return;
    }

    map.setView([userLocation.lat, userLocation.lng], 14, { animate: true });

    const userMarker = L.marker([userLocation.lat, userLocation.lng], { icon: userIcon });
    userMarker.bindPopup(
      `<div style="color: #071827; font-family: sans-serif; font-size: 13px;">
        <strong>Your Current Location</strong><br/>
        Lat: ${userLocation.lat.toFixed(4)}, Lng: ${userLocation.lng.toFixed(4)}<br/>
        H3 Cell: <code>${cell}</code><br/>
        Status: <strong>${statusLabel}</strong>
      </div>`
    );
    markersLayer.addLayer(userMarker);

    shelters.forEach((shelter) => {
      if (typeof shelter.lat === 'number' && typeof shelter.lng === 'number') {
        const marker = L.marker([shelter.lat, shelter.lng], { icon: shelterIcon });
        const distanceStr = shelter.distance_m !== undefined && shelter.distance_m !== null ? `Distance: ${Math.round(shelter.distance_m)}m<br/>` : '';
        const capacityStr = shelter.capacity !== undefined && shelter.capacity !== null ? `Capacity: ${shelter.capacity}<br/>` : '';
        const statusStr = shelter.open ? '<span style="color: green; font-weight: bold;">OPEN</span>' : '<span style="color: red;">CLOSED</span>';
        
        marker.bindPopup(
          `<div style="color: #071827; font-family: sans-serif; font-size: 13px;">
            <strong>${shelter.name}</strong> ${shelter.name_local ? `(${shelter.name_local})` : ''}<br/>
            Status: ${statusStr}<br/>
            ${distanceStr}
            ${capacityStr}
            <em style="font-size: 11px; color: #666;">${shelter.is_demo ? 'Demo Shelter Data' : 'Verified Shelter'}</em>
          </div>`
        );
        markersLayer.addLayer(marker);
      }
    });
  }, [userLocation, shelters, cell, statusLabel]);

  const mapModeLabel = isFallback
    ? 'OFFLINE DEMO'
    : isReplay
      ? 'REPLAY SCENARIO'
      : backendMode === 'mock'
        ? 'DEMO DATA'
        : backendMode === 'live'
          ? 'LIVE DATA'
          : 'UNKNOWN';

  return (
    <div style={{ position: 'relative', width: '100%', height: '360px', borderRadius: '12px', overflow: 'hidden' }}>
      <div
        style={{
          position: 'absolute',
          top: '12px',
          left: '12px',
          right: '12px',
          zIndex: 1000,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          pointerEvents: 'none',
        }}
      >
        <span
          className="map-chip"
          style={{ background: 'rgba(7, 24, 39, 0.85)', backdropFilter: 'blur(4px)', pointerEvents: 'auto' }}
        >
          H3 Cell: {cell}
        </span>
        <span
          className="map-chip"
          style={{ background: 'rgba(7, 24, 39, 0.85)', backdropFilter: 'blur(4px)', pointerEvents: 'auto' }}
        >
          {mapModeLabel}
        </span>
      </div>

      <div ref={mapContainerRef} style={{ width: '100%', height: '100%', background: '#071827' }} />

      {!userLocation && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 1001,
            background: 'rgba(7, 24, 39, 0.85)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#f87171',
            padding: '20px',
            textAlign: 'center',
          }}
        >
          <strong style={{ fontSize: '1rem', marginBottom: '4px' }}>Location Access Required</strong>
          <span style={{ fontSize: '0.85rem', color: '#94a3b8', maxWidth: '360px' }}>
            Please enable browser location permissions to render spatial hazard map and view nearby shelters.
          </span>
        </div>
      )}
    </div>
  );
};
