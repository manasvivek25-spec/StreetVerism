import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { getCells } from '../api/client';
import type { CellFeatureCollection, Shelter } from '../api/types';

interface MapViewProps {
  userLocation: { lat: number; lng: number } | null;
  shelters: Shelter[];
  cell: string;
  statusLabel: string;
  isReplay: boolean;
  isFallback: boolean;
  backendMode?: string;
  onSelectLocation?: (coords: { lat: number; lng: number }) => void;
}

const userIcon = L.divIcon({
  className: 'custom-user-marker',
  html: '<div style="background: #d7f34a; border: 3px solid #071827; width: 24px; height: 24px; border-radius: 50%; box-shadow: 0 0 14px rgba(215, 243, 74, 0.9); display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 800; color: #071827;">📍</div>',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

const shelterIcon = L.divIcon({
  className: 'custom-shelter-marker',
  html: '<div style="background: #0b1f32; border: 2px solid #22c55e; color: #4ade80; padding: 3px 8px; border-radius: 6px; font-size: 12px; font-weight: 700; white-space: nowrap; box-shadow: 0 2px 10px rgba(0,0,0,0.6);">⌖ Shelter</div>',
  iconSize: [70, 26],
  iconAnchor: [35, 13],
});

const STATUS_COLORS: Record<string, { fill: string; stroke: string }> = {
  official_hazard: { fill: '#ef4444', stroke: '#b91c1c' },
  likely_hazard: { fill: '#f97316', stroke: '#c2410c' },
  unverified: { fill: '#eab308', stroke: '#a16207' },
  contradicted: { fill: '#818cf8', stroke: '#4338ca' },
  clear: { fill: '#10b981', stroke: '#047857' },
};

export const MapView: React.FC<MapViewProps> = ({
  userLocation,
  shelters,
  cell,
  statusLabel,
  isReplay,
  isFallback,
  backendMode,
  onSelectLocation,
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const cellsLayerRef = useRef<L.GeoJSON | null>(null);
  const [cellsData, setCellsData] = useState<CellFeatureCollection | null>(null);

  // Fetch H3 cells feature collection
  useEffect(() => {
    let isCancelled = false;
    getCells()
      .then((data) => {
        if (!isCancelled && data && data.features) {
          setCellsData(data);
        }
      })
      .catch((err) => {
        console.warn('Failed to load cells for map layer:', err);
      });

    return () => {
      isCancelled = true;
    };
  }, []);

  // Initialize map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [13.015, 80.225],
        zoom: 13,
        zoomControl: true,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
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
        cellsLayerRef.current = null;
      }
    };
  }, []);

  // Render H3 cells layer
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !cellsData) return;

    if (cellsLayerRef.current) {
      map.removeLayer(cellsLayerRef.current);
      cellsLayerRef.current = null;
    }

    const geoJsonLayer = L.geoJSON(cellsData as any, {
      style: (feature) => {
        const featStatus = feature?.properties?.status || 'clear';
        const isCurrent = feature?.properties?.cell === cell;
        const col = STATUS_COLORS[featStatus] || STATUS_COLORS.clear;

        return {
          fillColor: col.fill,
          color: isCurrent ? '#ffffff' : col.stroke,
          weight: isCurrent ? 3 : 1.5,
          opacity: 0.9,
          fillOpacity: isCurrent ? 0.6 : featStatus === 'clear' ? 0.15 : 0.45,
        };
      },
      onEachFeature: (feature, layer) => {
        const props = feature?.properties || {};
        const pRisk = Math.round((props.p_hazard || 0) * 100);
        const statusClean = String(props.status || 'unknown').replace('_', ' ').toUpperCase();

        layer.bindPopup(
          `<div style="font-family: system-ui, sans-serif; font-size: 13px; color: #071827; line-height: 1.4;">
            <div style="font-weight: 800; font-size: 13px; color: ${STATUS_COLORS[props.status]?.stroke || '#000'}; text-transform: uppercase; margin-bottom: 4px;">
              ${statusClean}
            </div>
            <div><strong>H3 Cell:</strong> <code>${props.cell}</code></div>
            <div><strong>Posterior Hazard:</strong> ${pRisk}%</div>
            ${props.updated_at ? `<div style="font-size: 11px; color: #64748b; margin-top: 4px;">Sim Time: ${props.updated_at}</div>` : ''}
            ${onSelectLocation ? `<div style="margin-top: 6px; font-size: 11px; color: #2563eb; font-weight: 600;">(Click to assess this cell)</div>` : ''}
          </div>`
        );

        if (onSelectLocation) {
          layer.on('click', (e) => {
            onSelectLocation({ lat: e.latlng.lat, lng: e.latlng.lng });
          });
        }
      },
    });

    geoJsonLayer.addTo(map);
    cellsLayerRef.current = geoJsonLayer;
  }, [cellsData, cell, onSelectLocation]);

  // Render User and Shelters markers
  useEffect(() => {
    const map = mapInstanceRef.current;
    const markersLayer = markersLayerRef.current;
    if (!map || !markersLayer) return;

    markersLayer.clearLayers();

    if (userLocation) {
      map.setView([userLocation.lat, userLocation.lng], 13, { animate: true });

      const userMarker = L.marker([userLocation.lat, userLocation.lng], { icon: userIcon });
      userMarker.bindPopup(
        `<div style="color: #071827; font-family: system-ui, sans-serif; font-size: 13px;">
          <strong>📍 Your Evaluated Location</strong><br/>
          Lat: ${userLocation.lat.toFixed(4)}, Lng: ${userLocation.lng.toFixed(4)}<br/>
          H3 Cell: <code>${cell}</code><br/>
          Hazard Status: <strong>${statusLabel}</strong>
        </div>`
      );
      markersLayer.addLayer(userMarker);
    }

    shelters.forEach((shelter) => {
      if (typeof shelter.lat === 'number' && typeof shelter.lng === 'number') {
        const marker = L.marker([shelter.lat, shelter.lng], { icon: shelterIcon });
        const distanceStr =
          shelter.distance_m !== undefined && shelter.distance_m !== null
            ? `Distance: ${Math.round(shelter.distance_m)}m<br/>`
            : '';
        const capacityStr =
          shelter.capacity !== undefined && shelter.capacity !== null
            ? `Capacity: ${shelter.capacity}<br/>`
            : '';
        const statusStr = shelter.open
          ? '<span style="color: #16a34a; font-weight: bold;">OPEN</span>'
          : '<span style="color: #dc2626; font-weight: bold;">CLOSED</span>';
        const mapsLink = `https://www.google.com/maps/dir/?api=1&destination=${shelter.lat},${shelter.lng}`;

        marker.bindPopup(
          `<div style="color: #071827; font-family: system-ui, sans-serif; font-size: 13px; line-height: 1.4;">
            <strong>${shelter.name}</strong><br/>
            Status: ${statusStr}<br/>
            ${distanceStr}
            ${capacityStr}
            <div style="margin-top: 6px;">
              <a href="${mapsLink}" target="_blank" rel="noopener noreferrer" style="color: #2563eb; font-weight: 700; text-decoration: underline;">
                Open in Google Maps ↗
              </a>
            </div>
            <em style="font-size: 11px; color: #64748b; display: block; margin-top: 4px;">
              ${shelter.is_demo ? 'Demo Shelter Data' : 'Official Verified Shelter'}
            </em>
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
    <div style={{ position: 'relative', width: '100%', height: '380px', borderRadius: '12px', overflow: 'hidden' }}>
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
          style={{ background: 'rgba(7, 24, 39, 0.9)', backdropFilter: 'blur(4px)', pointerEvents: 'auto' }}
        >
          H3 Cell: {cell || '88618c4f1dfffff'}
        </span>
        <span
          className="map-chip"
          style={{ background: 'rgba(7, 24, 39, 0.9)', backdropFilter: 'blur(4px)', pointerEvents: 'auto' }}
        >
          {mapModeLabel}
        </span>
      </div>

      <div ref={mapContainerRef} style={{ width: '100%', height: '100%', background: '#071827' }} />
    </div>
  );
};
