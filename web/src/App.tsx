import { useEffect, useState } from 'react';
import './App.css';
import { ApiError, createCheckIn, createReport, getHealth, getState } from './api/client';
import type {
  CellStatus,
  CheckInState,
  ClaimType,
  HealthResponse,
  Language,
  StateResponse,
} from './api/types';
import { MapView } from './components/MapView';

const translations: Record<
  Language,
  {
    title: string;
    subtitle: string;
    status: string;
    instructions: string;
    shelters: string;
    safe: string;
    help: string;
  }
> = {
  en: {
    title: 'StreetVerism',
    subtitle: 'Tourist Safety & Crisis Companion',
    status: 'Local hazard status',
    instructions: 'Safety instructions',
    shelters: 'Nearby safe zones',
    safe: "I'm safe",
    help: 'I need help',
  },
  hi: {
    title: 'StreetVerism',
    subtitle: 'पर्यटक सुरक्षा साथी',
    status: 'स्थानीय खतरे की स्थिति',
    instructions: 'सुरक्षा निर्देश',
    shelters: 'पास के सुरक्षित स्थान',
    safe: 'मैं सुरक्षित हूँ',
    help: 'मुझे मदद चाहिए',
  },
  ta: {
    title: 'StreetVerism',
    subtitle: 'சுற்றுலாப் பயணி பாதுகாப்பு வழிகாட்டி',
    status: 'உள்ளூர் ஆபத்து நிலை',
    instructions: 'பாதுகாப்பு வழிமுறைகள்',
    shelters: 'அருகிலுள்ள பாதுகாப்பான இடங்கள்',
    safe: 'நான் பாதுகாப்பாக இருக்கிறேன்',
    help: 'எனக்கு உதவி தேவை',
  },
  fr: {
    title: 'StreetVerism',
    subtitle: 'Compagnon de sécurité touristique',
    status: 'État des risques locaux',
    instructions: 'Consignes de sécurité',
    shelters: 'Zones sûres à proximité',
    safe: 'Je suis en sécurité',
    help: 'J’ai besoin d’aide',
  },
  de: {
    title: 'StreetVerism',
    subtitle: 'Ihr lokaler Sicherheitsbegleiter',
    status: 'Lokale Gefahrenlage',
    instructions: 'Sicherheitshinweise',
    shelters: 'Sichere Orte in der Nähe',
    safe: 'Ich bin in Sicherheit',
    help: 'Ich brauche Hilfe',
  },
  ja: {
    title: 'StreetVerism',
    subtitle: '観光客向け安全ガイド',
    status: '地域の危険状況',
    instructions: '安全に関する指示',
    shelters: '近くの安全な避難場所',
    safe: '安全です',
    help: '助けが必要です',
  },
};

interface StatusVisual {
  label: string;
  icon: string;
  color: string;
  bg: string;
  description: string;
}

const statusVisuals: Record<CellStatus, StatusVisual> = {
  official_hazard: {
    label: 'OFFICIAL HAZARD',
    icon: '🚨',
    color: '#ef4444',
    bg: 'rgba(239, 68, 68, 0.15)',
    description: 'Confirmed hazard alert issued by disaster management authority. Evacuate or move to high ground.',
  },
  likely_hazard: {
    label: 'LIKELY HAZARD',
    icon: '⚠️',
    color: '#f97316',
    bg: 'rgba(249, 115, 22, 0.15)',
    description: 'High posterior hazard probability synthesized from corroborated observations and rainfall features.',
  },
  unverified: {
    label: 'UNVERIFIED',
    icon: '❓',
    color: '#eab308',
    bg: 'rgba(234, 179, 8, 0.15)',
    description: 'Community rumor / unverified social reports. Do NOT act on unverified rumors; wait for official updates.',
  },
  contradicted: {
    label: 'CONTRADICTED',
    icon: 'ℹ️',
    color: '#818cf8',
    bg: 'rgba(129, 140, 248, 0.15)',
    description: 'Prior social reports contradicted by official survey observations.',
  },
  clear: {
    label: 'CLEAR',
    icon: '🛡️',
    color: '#10b981',
    bg: 'rgba(16, 185, 129, 0.15)',
    description: 'No active hazard indicators detected in this area. Conditions normal.',
  },
};

const PRESET_DEMO_LOCATIONS = [
  { id: 'adyar', label: 'Adyar (Official Hazard)', lat: 13.015, lng: 80.225, hint: 'Golden path peak emergency zone' },
  { id: 'central', label: 'Central Zone (Unverified Rumor)', lat: 13.055, lng: 80.225, hint: 'Viral rumor cell' },
  { id: 'calm', label: 'Calm Zone (Clear)', lat: 13.100, lng: 80.160, hint: 'Clear weather area' },
  { id: 'velachery', label: 'Velachery (Relief Center)', lat: 12.9815, lng: 80.218, hint: 'Near demo relief center' },
];

const fallbackState: StateResponse = {
  cell: '88618c4f1dfffff',
  status: 'official_hazard',
  p_hazard: 0.99,
  headline_key: 'MOVE_TO_HIGHER_GROUND',
  alerts: [
    {
      id: 'alt_rep_adyar_extreme',
      source: 'replay',
      sender: 'State Disaster Authority (replay)',
      hazard: 'flood',
      severity: 'extreme',
      urgency: 'immediate',
      certainty: 'observed',
      area: {
        type: 'Polygon',
        coordinates: [[[80.21, 13.002], [80.245, 13.002], [80.245, 13.03], [80.21, 13.03], [80.21, 13.002]]],
      },
      instruction_keys: ['MOVE_TO_HIGHER_GROUND', 'AVOID_FLOODED_ROADS'],
      params: {},
      sent_at: '2023-12-04T09:00:00+00:00',
      expires_at: '2023-12-05T06:00:00+00:00',
      supersedes: null,
      published_by: 'state-operator',
      is_replay: true,
    },
  ],
  instructions: [
    {
      key: 'MOVE_TO_HIGHER_GROUND',
      text: 'Move to higher ground immediately. Do not wait.',
      reviewed: true,
      original_en: null,
    },
    {
      key: 'AVOID_FLOODED_ROADS',
      text: 'Avoid flooded roads and underpasses.',
      reviewed: true,
      original_en: null,
    },
  ],
  evidence: [
    { type: 'official', summary: 'Official Flood Alert from State Disaster Authority (replay)', age_s: 1800, weight: 3.5 },
    { type: 'rain', summary: 'Rain 49.0 mm in 3 h, 81.3 mm in 24 h; flood-prone area', age_s: 0, weight: 4.27 },
  ],
  nearest_shelters: [
    {
      id: 'sh_chennai_03',
      name: 'Demo Cyclone Center - Saidapet',
      name_local: 'Demo Cyclone Center - Saidapet',
      lat: 13.021,
      lng: 80.223,
      open: true,
      is_demo: true,
      capacity: 420,
      distance_m: 701.5,
    },
    {
      id: 'sh_chennai_01',
      name: 'Demo Relief Center - Velachery',
      name_local: 'Demo Relief Center - Velachery',
      lat: 12.9815,
      lng: 80.218,
      open: true,
      is_demo: true,
      capacity: 350,
      distance_m: 3801.5,
    },
  ],
  is_replay: true,
  generated_at: '2023-12-04T09:30:00+00:00',
  server_time: new Date().toISOString(),
};

function getGuardedDeviceId(): string {
  const storageKey = 'streetverism_device_id';
  try {
    const existing = localStorage.getItem(storageKey);
    if (existing && existing.trim().length > 0) return existing;
  } catch {
    // LocalStorage blocked (private window/iframe)
  }

  let id = '';
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    id = crypto.randomUUID();
  } else {
    id = 'dev-' + Math.random().toString(36).substring(2, 11) + '-' + Date.now();
  }

  try {
    localStorage.setItem(storageKey, id);
  } catch {
    // Ignore storage failure
  }
  return id;
}

function getBrowserLocation(): Promise<{ lat: number; lng: number }> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Geolocation is not supported by your browser.'));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        resolve({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        });
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) {
          reject(new Error('Location permission denied.'));
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          reject(new Error('Location unavailable.'));
        } else if (err.code === err.TIMEOUT) {
          reject(new Error('Location request timed out.'));
        } else {
          reject(new Error(err.message));
        }
      },
      { enableHighAccuracy: true, timeout: 6000, maximumAge: 60000 }
    );
  });
}

function App() {
  const [language, setLanguage] = useState<Language>('en');
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);

  // Location state: defaults to Adyar hazard zone for instant demo readiness
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number }>({
    lat: PRESET_DEMO_LOCATIONS[0].lat,
    lng: PRESET_DEMO_LOCATIONS[0].lng,
  });
  const [selectedPreset, setSelectedPreset] = useState<string>('adyar');
  const [usingRealGps, setUsingRealGps] = useState<boolean>(false);
  const [locationNotice, setLocationNotice] = useState<string | null>(null);

  const [stateData, setStateData] = useState<StateResponse | null>(null);
  const [backendHealth, setBackendHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isFallback, setIsFallback] = useState<boolean>(false);

  // Check-in state & rate limiting
  const [checkInSubmitting, setCheckInSubmitting] = useState<boolean>(false);
  const [checkInCooldown, setCheckInCooldown] = useState<number>(0);
  const [checkInFeedback, setCheckInFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Incident report state
  const [claimType, setClaimType] = useState<ClaimType>('flooded');
  const [reportText, setReportText] = useState<string>('');
  const [reportSubmitting, setReportSubmitting] = useState<boolean>(false);
  const [reportFeedback, setReportFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const t = translations[language] || translations.en;

  // Rate limit cooldown countdown timer
  useEffect(() => {
    if (checkInCooldown <= 0) return;
    const timer = setInterval(() => {
      setCheckInCooldown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [checkInCooldown]);

  // Check health and mode on mount
  useEffect(() => {
    let isCancelled = false;
    getHealth()
      .then((h) => {
        if (!isCancelled) setBackendHealth(h);
      })
      .catch(() => {
        if (!isCancelled) setBackendHealth(null);
      });
    return () => {
      isCancelled = true;
    };
  }, []);

  // Attempt real GPS once on mount if in Chennai coverage area
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('demo') === '1') return;

    getBrowserLocation()
      .then((loc) => {
        // If outside Chennai bbox, keep demo coordinate to ensure MVP scenario visibility
        if (loc.lat < 12.8 || loc.lat > 13.3 || loc.lng < 80.1 || loc.lng > 80.4) {
          setLocationNotice(
            `Device GPS detected (${loc.lat.toFixed(2)}, ${loc.lng.toFixed(2)}) is outside the Chennai crisis coverage area. Defaulted to demo zone.`
          );
        } else {
          setUserLocation(loc);
          setSelectedPreset('gps');
          setUsingRealGps(true);
        }
      })
      .catch(() => {
        // Expected on laptops or permission denials; demo preset handles it seamlessly
      });
  }, []);

  const [refreshIndex, setRefreshIndex] = useState<number>(0);
  const reloadState = () => {
    setLoading(true);
    setRefreshIndex((k) => k + 1);
  };

  // Fetch state for current location and language (with 10s auto-polling for published alerts)
  useEffect(() => {
    let isCancelled = false;

    const pollState = () => {
      getState(userLocation.lat, userLocation.lng, language)
        .then((data) => {
          if (!isCancelled) {
            setStateData(data);
            setError(null);
            setIsFallback(false);
            setLoading(false);
          }
        })
        .catch((err: unknown) => {
          if (!isCancelled) {
            const msg = err instanceof Error ? err.message : 'Unable to connect to safety server.';
            setError(msg);
            setStateData(fallbackState);
            setIsFallback(true);
            setLoading(false);
          }
        });
    };

    pollState();
    const interval = setInterval(pollState, 10000);

    return () => {
      isCancelled = true;
      clearInterval(interval);
    };
  }, [userLocation, language, refreshIndex]);

  const handleSelectPreset = (presetId: string) => {
    const found = PRESET_DEMO_LOCATIONS.find((p) => p.id === presetId);
    if (found) {
      setSelectedPreset(found.id);
      setUsingRealGps(false);
      setUserLocation({ lat: found.lat, lng: found.lng });
    }
  };

  const handleUseRealGps = () => {
    getBrowserLocation()
      .then((loc) => {
        setUserLocation(loc);
        setSelectedPreset('gps');
        setUsingRealGps(true);
        setLocationNotice(null);
      })
      .catch((err: Error) => {
        setLocationNotice(`Location access failed: ${err.message}. Using simulated demo coordinates.`);
      });
  };

  const handleCheckIn = async (state: CheckInState) => {
    if (checkInSubmitting || checkInCooldown > 0) return;
    setCheckInSubmitting(true);
    setCheckInFeedback(null);

    try {
      const deviceId = getGuardedDeviceId();
      const response = await createCheckIn({
        device_id: deviceId,
        lat: userLocation.lat,
        lng: userLocation.lng,
        state,
        language,
        group_size: 1,
      });

      if (response && response.id) {
        const timeStr = new Date(response.recorded_at).toLocaleTimeString();
        setCheckInFeedback({
          type: 'success',
          message:
            state === 'need_help'
              ? `🆘 Help request submitted (ID: ${response.id}, ${timeStr}). It will appear on the authority dashboard within ~10 seconds.`
              : `✓ Safe status recorded (ID: ${response.id}, ${timeStr}).`,
        });
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        const wait = err.retryAfter || 60;
        setCheckInCooldown(wait);
        setCheckInFeedback({
          type: 'error',
          message: `⚠️ Rate limit exceeded. Please wait ${wait} seconds before retrying.`,
        });
      } else {
        const msg = err instanceof Error ? err.message : 'Check-in failed.';
        setCheckInFeedback({ type: 'error', message: msg });
      }
    } finally {
      setCheckInSubmitting(false);
    }
  };

  const handleReportSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (reportSubmitting) return;

    setReportSubmitting(true);
    setReportFeedback(null);

    try {
      const deviceId = getGuardedDeviceId();
      const response = await createReport({
        device_id: deviceId,
        lat: userLocation.lat,
        lng: userLocation.lng,
        claim: claimType,
        text: reportText.trim() || undefined,
      });

      if (response && response.accepted) {
        setReportFeedback({
          type: 'success',
          message: `Observation registered for cell ${response.cell} (Status: ${response.status}). Bayesian engine corroboration pending.`,
        });
        setReportText('');
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setReportFeedback({
          type: 'error',
          message: `⚠️ Rate limit reached. Please wait before submitting another report.`,
        });
      } else {
        const msg = err instanceof Error ? err.message : 'Report submission failed.';
        setReportFeedback({ type: 'error', message: msg });
      }
    } finally {
      setReportSubmitting(false);
    }
  };

  const activeState = stateData ?? fallbackState;
  const statusInfo = statusVisuals[activeState.status] ?? statusVisuals.clear;
  const isReplayMode = activeState.is_replay || backendHealth?.is_replay || backendHealth?.mode === 'replay';
  const replayDisclaimer =
    backendHealth?.replay?.disclaimer || 'Simulated data based loosely on a past event, not real or official.';

  const scrollToSection = (id: string) => {
    setActiveTab(id);
    setMobileMenuOpen(false);
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="dashboard-container">
      {/* Mobile Top Header */}
      <div className="mobile-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span className="sidebar-brand-icon">S</span>
          <span style={{ fontWeight: 800, color: '#fff' }}>StreetVerism</span>
        </div>
        <button className="menu-toggle" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
          {mobileMenuOpen ? '✕ Close' : '☰ Menu'}
        </button>
      </div>

      {/* Sticky Sidebar */}
      <aside className={`sidebar ${mobileMenuOpen ? 'mobile-open' : ''}`}>
        <a className="sidebar-brand" href="#">
          <span className="sidebar-brand-icon">S</span>
          <span className="sidebar-brand-text">StreetVerism</span>
        </a>

        <nav className="sidebar-nav">
          <button
            className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => scrollToSection('dashboard')}
          >
            <span className="nav-icon">📊</span>
            <span>Safety Dashboard</span>
          </button>
          <button
            className={`nav-item ${activeTab === 'map-section' ? 'active' : ''}`}
            onClick={() => scrollToSection('map-section')}
          >
            <span className="nav-icon">🗺️</span>
            <span>Hazard Map</span>
          </button>
          <button
            className={`nav-item ${activeTab === 'instructions-section' ? 'active' : ''}`}
            onClick={() => scrollToSection('instructions-section')}
          >
            <span className="nav-icon">📢</span>
            <span>Instructions</span>
          </button>
          <button
            className={`nav-item ${activeTab === 'shelters-section' ? 'active' : ''}`}
            onClick={() => scrollToSection('shelters-section')}
          >
            <span className="nav-icon">⌖</span>
            <span>Safe Shelters</span>
          </button>
          <button
            className={`nav-item ${activeTab === 'checkin-section' ? 'active' : ''}`}
            onClick={() => scrollToSection('checkin-section')}
          >
            <span className="nav-icon">✓</span>
            <span>Status Check-in</span>
          </button>
          <button
            className={`nav-item ${activeTab === 'report-section' ? 'active' : ''}`}
            onClick={() => scrollToSection('report-section')}
          >
            <span className="nav-icon">📝</span>
            <span>Report Hazard</span>
          </button>
          <a
            className="nav-item"
            href="/console"
            style={{ textDecoration: 'none', color: '#94a3b8' }}
          >
            <span className="nav-icon">⚙️</span>
            <span>Authority Console</span>
          </a>
        </nav>

        <div className="sidebar-footer">
          <div><strong>StreetVerism Companion</strong></div>
          <div>Multi-source Bayesian Trust Network</div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content" id="dashboard">
        <header className="header-bar">
          <div className="header-title-group">
            <h1>Tourist Safety Dashboard</h1>
            <p className="header-subtitle">
              {isFallback
                ? 'Backend API offline — displaying fallback demonstration.'
                : isReplayMode
                  ? 'Historical Cyclone Michaung Replay (Illustrative reconstruction).'
                  : backendHealth?.mode === 'mock'
                    ? 'Backend running in MOCK mode.'
                    : 'Connected to live StreetVerism safety network.'}
            </p>
          </div>

          <div className="badge-group">
            {isFallback ? (
              <span className="mode-badge fallback-badge">OFFLINE · DEMO FALLBACK</span>
            ) : isReplayMode ? (
              <span className="mode-badge" style={{ background: '#7c3aed', color: '#ffffff' }}>
                REPLAY: ILLUSTRATIVE RECONSTRUCTION
              </span>
            ) : backendHealth?.mode === 'mock' ? (
              <span className="mode-badge" style={{ background: '#f59e0b', color: '#071827' }}>
                MOCK DATA
              </span>
            ) : backendHealth?.mode === 'live' ? (
              <span className="mode-badge live-badge">LIVE NETWORK</span>
            ) : (
              <span className="mode-badge" style={{ background: '#64748b', color: '#fff' }}>
                CONNECTING...
              </span>
            )}
          </div>
        </header>

        {/* Replay / Mock Honest Disclaimer Banner */}
        {isReplayMode && (
          <div className="disclaimer-banner" role="status">
            <span style={{ fontSize: '1.2rem' }}>ℹ️</span>
            <div>
              <strong>Replay Mode Active:</strong> {replayDisclaimer}
            </div>
          </div>
        )}

        {/* Demo Area & Location Picker */}
        <div className="demo-picker-card">
          <div className="demo-picker-title">
            <span>📍 Evaluated Demo Area:</span>
          </div>
          <div className="demo-picker-btns">
            {PRESET_DEMO_LOCATIONS.map((preset) => (
              <button
                key={preset.id}
                className={`demo-btn ${selectedPreset === preset.id ? 'active' : ''}`}
                onClick={() => handleSelectPreset(preset.id)}
                title={preset.hint}
              >
                {preset.label}
              </button>
            ))}
            <button
              className={`demo-btn ${usingRealGps ? 'active' : ''}`}
              onClick={handleUseRealGps}
              title="Assess using your device's real GPS sensor"
            >
              📡 Use Real GPS
            </button>
          </div>
        </div>

        {locationNotice && (
          <div className="notice-box" style={{ marginBottom: '16px' }}>
            {locationNotice}
          </div>
        )}

        {error && (
          <div className="dark-error-banner" role="alert">
            <div>
              <strong>⚠️ Connection Alert:</strong> {error}
            </div>
            <button
              className="retry-button"
              onClick={reloadState}
              disabled={loading}
            >
              {loading ? 'Retrying...' : 'Retry'}
            </button>
          </div>
        )}

        {/* Distinct Warning for Unverified / Contradicted Rumor Cells */}
        {(activeState.status === 'unverified' || activeState.status === 'contradicted') && (
          <div className="rumor-warning-card">
            <div className="rumor-warning-title">
              <span>⚠️ UNVERIFIED SOCIAL MEDIA REPORTS</span>
            </div>
            <p className="rumor-warning-body">
              This cell contains community reports that have NOT been confirmed by official authorities. StreetVerism's Bayesian trust engine has clustered and de-weighted these claims. Exercise extreme caution and do not act on social rumors until officially corroborated.
            </p>
          </div>
        )}

        {/* Summary Metric Cards */}
        <div className="summary-cards-grid">
          <div className="summary-card" style={{ borderLeft: `4px solid ${statusInfo.color}` }}>
            <div className="card-label">Current Hazard Status</div>
            <div
              className="card-value"
              style={{
                color: statusInfo.color,
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <span>{statusInfo.icon}</span>
              <span>{statusInfo.label}</span>
            </div>
            <div className="card-subtext">H3 Cell: {activeState.cell}</div>
          </div>

          <div className="summary-card">
            <div className="card-label">Posterior Hazard Risk</div>
            <div className="card-value" style={{ color: '#d7f34a' }}>
              {Math.round(activeState.p_hazard * 100)}%
            </div>
            <div className="card-subtext">Bayesian fused probability</div>
          </div>

          <div className="summary-card">
            <div className="card-label">Nearby Open Shelters</div>
            <div className="card-value">
              {activeState.nearest_shelters.filter((s) => s.open).length}
            </div>
            <div className="card-subtext">{activeState.nearest_shelters.length} Total Registered</div>
          </div>

          <div className="summary-card">
            <div className="card-label">Official Alerts</div>
            <div className="card-value">{activeState.alerts.length}</div>
            <div className="card-subtext">Active CAP advisories</div>
          </div>
        </div>

        {/* Map & Language Grid */}
        <div className="dashboard-grid" id="map-section">
          {/* Spatial Leaflet Map with H3 Polygons */}
          <div className="map-panel">
            <div className="panel-header">
              <div className="panel-title-group">
                <span className="panel-title-icon">🗺️</span>
                <h2>Spatial Hazard Map (H3 Resolution 8)</h2>
              </div>
              <span className="map-chip">
                Lat: {userLocation.lat.toFixed(4)}, Lng: {userLocation.lng.toFixed(4)}
              </span>
            </div>

            <MapView
              userLocation={userLocation}
              shelters={activeState.nearest_shelters}
              cell={activeState.cell}
              statusLabel={statusInfo.label}
              isReplay={isReplayMode}
              isFallback={isFallback}
              backendMode={backendHealth?.mode}
              onSelectLocation={(coords) => {
                setSelectedPreset('custom');
                setUserLocation(coords);
              }}
            />

            <p className="notice-box">
              Polygons represent spatial H3 resolution 8 cells colored by Bayesian hazard classification (Red: Official Hazard, Yellow: Unverified Rumors, Green: Clear). Click any cell or shelter to inspect.
            </p>
          </div>

          {/* Right Side: Hazard Level & Language Picker */}
          <div className="side-panels-column">
            {/* Status & Evidence Breakdown */}
            <div className="info-card">
              <div className="status-header-box">
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 750, textTransform: 'uppercase' }}>
                    Hazard Assessment
                  </div>
                  <h3 style={{ margin: 0, color: statusInfo.color, fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>{statusInfo.icon}</span>
                    <span>{statusInfo.label}</span>
                  </h3>
                </div>
                <span
                  className="status-badge-tag"
                  style={{
                    backgroundColor: statusInfo.bg,
                    color: statusInfo.color,
                    border: `1px solid ${statusInfo.color}`,
                    fontWeight: 700,
                  }}
                >
                  {activeState.status.toUpperCase()}
                </span>
              </div>

              <p style={{ fontSize: '0.88rem', color: '#cbd5e1', lineHeight: 1.5, margin: '0 0 14px 0' }}>
                {statusInfo.description}
              </p>

              {/* Expandable "Why?" Evidence Accordion */}
              <details className="why-accordion" open>
                <summary className="why-summary">
                  🔍 Why this status? View Bayesian Evidence ({activeState.evidence.length})
                </summary>
                <div className="why-content">
                  <div className="evidence-list">
                    {activeState.evidence.length > 0 ? (
                      activeState.evidence.map((ev, idx) => (
                        <div key={idx} className="evidence-item">
                          <div className="evidence-type" style={{ textTransform: 'capitalize' }}>
                            {ev.type === 'official' ? '🏛️ Official Alert' : ev.type === 'rain' ? '🌧️ Weather Feature' : '👥 Crowd Cluster'}
                          </div>
                          <div style={{ color: '#cbd5e1', marginTop: '2px' }}>{ev.summary}</div>
                          <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '4px' }}>
                            Age: {Math.round(ev.age_s / 60)} min · Bayesian LLR Weight: {ev.weight}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div style={{ fontSize: '0.85rem', color: '#64748b' }}>No active evidence items.</div>
                    )}
                  </div>
                </div>
              </details>
            </div>

            {/* Language Selector */}
            <div className="info-card" id="lang-section">
              <h3 style={{ margin: '0 0 8px 0', fontSize: '1.05rem', color: '#fff' }}>
                🌐 Language / भाषा / மொழி
              </h3>
              <p style={{ fontSize: '0.82rem', color: '#94a3b8', margin: '0 0 14px 0' }}>
                Select language for instructions. Human-reviewed: en, ta, hi. Machine-translated: de, fr, ja.
              </p>

              <select
                className="dark-select"
                value={language}
                onChange={(e) => setLanguage(e.target.value as Language)}
                disabled={loading}
              >
                <option value="de">🇩🇪 Deutsch (German) · Machine-translated</option>
                <option value="en">🇬🇧 English · Human-reviewed</option>
                <option value="ta">🇮🇳 தமிழ் (Tamil) · Human-reviewed</option>
                <option value="hi">🇮🇳 हिन्दी (Hindi) · Human-reviewed</option>
                <option value="fr">🇫🇷 Français (French) · Machine-translated</option>
                <option value="ja">🇯🇵 日本語 (Japanese) · Machine-translated</option>
              </select>
            </div>
          </div>
        </div>

        {/* Instructions & Shelters Grid */}
        <div className="bottom-grid" id="instructions-section">
          {/* Instructions Panel */}
          <div className="action-card">
            <div className="panel-title-group" style={{ marginBottom: '16px' }}>
              <span className="panel-title-icon">↗</span>
              <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#fff' }}>{t.instructions}</h2>
            </div>

            {activeState.instructions.length > 0 ? (
              <ul className="instruction-list" style={{ paddingLeft: '18px' }}>
                {activeState.instructions.map((inst, idx) => (
                  <li key={inst.key || idx} style={{ marginBottom: '14px' }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', flexWrap: 'wrap', gap: '6px' }}>
                      <strong style={{ color: '#f1f5f9', fontSize: '0.95rem' }}>{inst.text}</strong>
                      {inst.reviewed ? (
                        <span className="badge-reviewed">✓ Reviewed</span>
                      ) : (
                        <span className="badge-unreviewed">⚠️ Machine-translated</span>
                      )}
                    </div>
                    {!inst.reviewed && (
                      <div className="unreviewed-warning-notice">
                        Machine translation. Verify critical details with emergency personnel.
                      </div>
                    )}
                    {!inst.reviewed && inst.original_en && (
                      <div className="original-en-text">
                        Original English: "{inst.original_en}"
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="card-subtext">No active safety instructions for this sector.</p>
            )}

            <p className="notice-box">
              {isReplayMode
                ? 'Replay instructions reconstructed from historical disaster event. Follow local civil defence.'
                : 'Follow official directives and civil defence instructions immediately.'}
            </p>
          </div>

          {/* Shelters Panel with Open in Maps Links */}
          <div className="action-card" id="shelters-section">
            <div className="panel-title-group" style={{ marginBottom: '16px' }}>
              <span className="panel-title-icon">⌖</span>
              <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#fff' }}>{t.shelters}</h2>
            </div>

            {activeState.nearest_shelters.length > 0 ? (
              activeState.nearest_shelters.map((shelter, idx) => {
                const mapsUrl = `https://www.google.com/maps/dir/?api=1&destination=${shelter.lat},${shelter.lng}`;
                const showLocalName = shelter.name_local && shelter.name_local !== shelter.name;

                return (
                  <div
                    key={shelter.id || idx}
                    style={{ padding: '14px 0', borderBottom: '1px solid #1e293b' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                      <div>
                        <h3 style={{ margin: 0, fontSize: '0.98rem', color: '#ffffff' }}>
                          {shelter.name}
                          {showLocalName && (
                            <span style={{ color: '#94a3b8', fontSize: '0.85rem', marginLeft: '6px' }}>
                              ({shelter.name_local})
                            </span>
                          )}
                        </h3>
                        <div style={{ fontSize: '0.82rem', color: '#94a3b8', marginTop: '4px' }}>
                          {shelter.open ? (
                            <span style={{ color: '#4ade80', fontWeight: 700 }}>🟢 Open</span>
                          ) : (
                            <span style={{ color: '#f87171', fontWeight: 700 }}>🔴 Closed</span>
                          )}
                          {shelter.distance_m !== undefined && shelter.distance_m !== null && (
                            <span> · {Math.round(shelter.distance_m)}m away</span>
                          )}
                          {shelter.capacity !== undefined && shelter.capacity !== null && (
                            <span> · Capacity: {shelter.capacity}</span>
                          )}
                        </div>
                      </div>

                      <span
                        style={{
                          fontSize: '0.7rem',
                          color: shelter.is_demo ? '#94a3b8' : '#4ade80',
                          background: '#071827',
                          padding: '4px 8px',
                          borderRadius: '6px',
                          border: '1px solid #1e293b',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {shelter.is_demo ? 'DEMO SHELTER' : 'VERIFIED'}
                      </span>
                    </div>

                    <a
                      href={mapsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-open-maps"
                    >
                      🗺️ Open in Google Maps ↗
                    </a>
                  </div>
                );
              })
            ) : (
              <p className="card-subtext">No registered shelters found in this sector.</p>
            )}

            <p className="notice-box">
              Tap "Open in Google Maps" to launch turn-by-turn navigation directly on your mobile device.
            </p>
          </div>
        </div>

        {/* Actions Grid: Check-in & Incident Report */}
        <div className="bottom-grid">
          {/* Check-in Card */}
          <div className="action-card" id="checkin-section">
            <div className="card-label">STATUS CHECK-IN</div>
            <h2 style={{ margin: '4px 0 8px 0', color: '#fff', fontSize: '1.25rem' }}>Are you safe?</h2>
            <p className="card-subtext">
              Transmits your coordinates and status to the disaster response console dashboard.
            </p>

            <div className="checkin-btn-group">
              <button
                className="btn-safe"
                onClick={() => void handleCheckIn('safe')}
                disabled={checkInSubmitting || checkInCooldown > 0}
              >
                {checkInSubmitting ? 'Transmitting...' : `✓ ${t.safe}`}
              </button>
              <button
                className="btn-help"
                onClick={() => void handleCheckIn('need_help')}
                disabled={checkInSubmitting || checkInCooldown > 0}
              >
                {checkInSubmitting
                  ? 'Transmitting...'
                  : checkInCooldown > 0
                    ? `Wait ${checkInCooldown}s`
                    : `🚨 ${t.help}`}
              </button>
            </div>

            {checkInFeedback && (
              <div
                className={checkInFeedback.type === 'error' ? 'dark-feedback-error' : 'dark-feedback-success'}
                role="status"
              >
                {checkInFeedback.message}
              </div>
            )}

            <p className="notice-box">
              ⚠️ In an immediate life-threatening emergency, call local emergency services (112) directly.
            </p>
          </div>

          {/* Incident Report Card */}
          <div className="action-card" id="report-section">
            <div className="card-label">COMMUNITY OBSERVATION</div>
            <h2 style={{ margin: '4px 0 8px 0', color: '#fff', fontSize: '1.25rem' }}>Report Local Hazard</h2>
            <p className="card-subtext">
              Crowd observations are clustered and corroborated before influencing trust engine status.
            </p>

            <form className="report-form-group" onSubmit={(e) => void handleReportSubmit(e)}>
              <div>
                <div className="form-label">Observation Type</div>
                <select
                  className="dark-select"
                  value={claimType}
                  onChange={(e) => setClaimType(e.target.value as ClaimType)}
                  disabled={reportSubmitting}
                >
                  <option value="flooded">🌊 Flooded Roadway / Waterlogging</option>
                  <option value="blocked">🚧 Blocked Path / Fallen Debris</option>
                  <option value="safe">🛡️ Clear &amp; Passable</option>
                </select>
              </div>

              <div>
                <div className="form-label">Details (optional)</div>
                <textarea
                  className="dark-textarea"
                  rows={2}
                  placeholder="Water depth, road name, or current condition (max 500 chars)..."
                  value={reportText}
                  onChange={(e) => setReportText(e.target.value)}
                  disabled={reportSubmitting}
                  maxLength={500}
                />
              </div>

              <button type="submit" className="btn-submit" disabled={reportSubmitting}>
                {reportSubmitting ? 'Submitting Report...' : 'Submit Observation'}
              </button>

              {reportFeedback && (
                <div
                  className={reportFeedback.type === 'error' ? 'dark-feedback-error' : 'dark-feedback-success'}
                  role="status"
                >
                  {reportFeedback.message}
                </div>
              )}
            </form>
          </div>
        </div>

        {/* Dashboard Footer */}
        <footer
          style={{
            marginTop: '40px',
            padding: '20px 0',
            borderTop: '1px solid #1e293b',
            display: 'flex',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px',
            color: '#64748b',
            fontSize: '0.8rem',
          }}
        >
          <div>STREETVERISM · TOURIST CRISIS NETWORK</div>
          <div>
            {isReplayMode
              ? 'Replay Scenario · Illustrative Reconstruction · Not Official Data'
              : 'StreetVerism Safety Network'}
          </div>
        </footer>
      </main>
    </div>
  );
}

export default App;