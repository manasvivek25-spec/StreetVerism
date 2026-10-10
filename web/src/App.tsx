import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { createCheckIn, createReport, getHealth, getState } from './api/client'
import type { CellStatus, CheckInState, ClaimType, HealthResponse, Language, StateResponse } from './api/types'
import { MapView } from './components/MapView'

const translations: Record<Language, { title: string; subtitle: string; status: string; instructions: string; shelters: string; safe: string; help: string }> = {
  en: { title: 'StreetVerism', subtitle: 'Your local safety companion', status: 'Local hazard status', instructions: 'Safety instructions', shelters: 'Nearby safe zones', safe: "I'm safe", help: 'I need help' },
  hi: { title: 'StreetVerism', subtitle: 'आपका स्थानीय सुरक्षा सहायक', status: 'स्थानीय खतरे की स्थिति', instructions: 'सुरक्षा निर्देश', shelters: 'पास के सुरक्षित स्थान', safe: 'मैं सुरक्षित हूँ', help: 'मुझे मदद चाहिए' },
  ta: { title: 'StreetVerism', subtitle: 'உங்கள் உள்ளூர் பாதுகாப்பு உதவியாளர்', status: 'உள்ளூர் ஆபத்து நிலை', instructions: 'பாதுகாப்பு வழிமுறைகள்', shelters: 'அருகிலுள்ள பாதுகாப்பான இடங்கள்', safe: 'நான் பாதுகாப்பாக இருக்கிறேன்', help: 'எனக்கு உதவி தேவை' },
  fr: { title: 'StreetVerism', subtitle: 'Votre compagnon de sécurité local', status: 'État des risques locaux', instructions: 'Consignes de sécurité', shelters: 'Zones sûres à proximité', safe: 'Je suis en sécurité', help: "J’ai besoin d’aide" },
  de: { title: 'StreetVerism', subtitle: 'Ihr lokaler Sicherheitsbegleiter', status: 'Lokale Gefahrenlage', instructions: 'Sicherheitshinweise', shelters: 'Sichere Orte in der Nähe', safe: 'Ich bin in Sicherheit', help: 'Ich brauche Hilfe' },
  ja: { title: 'StreetVerism', subtitle: '地域の安全をサポート', status: '地域の危険状況', instructions: '安全に関する指示', shelters: '近くの安全な避難場所', safe: '安全です', help: '助けが必要です' },
}

const statusDisplayLabels: Record<CellStatus, { label: string; description: string }> = {
  official_hazard: { label: 'OFFICIAL HAZARD', description: 'Confirmed hazard alert issued by disaster management authority.' },
  likely_hazard: { label: 'LIKELY HAZARD', description: 'High posterior hazard probability based on evidence synthesis.' },
  unverified: { label: 'UNVERIFIED', description: 'Community report received, pending independent verification.' },
  contradicted: { label: 'CONTRADICTED', description: 'Reports contradicted by recent field observations.' },
  clear: { label: 'CLEAR', description: 'No active hazard indicators detected in this area.' },
}

const fallbackState: StateResponse = {
  cell: '88618925d3fffff',
  status: 'unverified',
  p_hazard: 0.45,
  headline_key: 'UNVERIFIED_WARNING',
  alerts: [],
  instructions: [
    { key: 'AVOID_FLOODED_ROADS', text: 'Avoid flooded roads and underpasses.', reviewed: true },
    { key: 'DO_NOT_CROSS_WATER', text: 'Never walk or drive through floodwater.', reviewed: true },
    { key: 'FOLLOW_OFFICIAL_ONLY', text: 'Follow verified official announcements.', reviewed: true },
    { key: 'KEEP_PHONE_CHARGED', text: 'Keep your phone charged and accessible.', reviewed: true },
  ],
  evidence: [
    { type: 'crowd', summary: 'Community flood report', age_s: 120, weight: 1.2 }
  ],
  nearest_shelters: [
    {
      id: 'sh-1',
      name: 'Demo Community Shelter',
      name_local: 'Demo Community Shelter',
      lat: 12.9815,
      lng: 80.2180,
      open: true,
      is_demo: true,
      capacity: 350,
      distance_m: 450,
    }
  ],
  is_replay: true,
  generated_at: new Date().toISOString(),
  server_time: new Date().toISOString(),
}

function getDeviceId(): string {
  const storageKey = 'streetverism_device_id'
  let id = localStorage.getItem(storageKey)
  if (!id) {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      id = crypto.randomUUID()
    } else {
      id = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0
        const v = c === 'x' ? r : (r & 0x3) | 0x8
        return v.toString(16)
      })
    }
    localStorage.setItem(storageKey, id)
  }
  return id
}

function getCurrentLocation(): Promise<{ lat: number; lng: number }> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Geolocation is not supported by your browser.'))
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        resolve({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        })
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) {
          reject(new Error('Location permission denied. Please allow location access in your browser.'))
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          reject(new Error('Location information is currently unavailable from your device.'))
        } else if (err.code === err.TIMEOUT) {
          reject(new Error('Location request timed out. Please check GPS signal.'))
        } else {
          reject(new Error('Unable to retrieve location: ' + err.message))
        }
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    )
  })
}

function App() {
  const [language, setLanguage] = useState<Language>('en')
  const [activeTab, setActiveTab] = useState<string>('dashboard')
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false)
  
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null)
  const [locationError, setLocationError] = useState<string | null>(null)
  const [stateData, setStateData] = useState<StateResponse | null>(null)
  const [backendHealth, setBackendHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [isFallback, setIsFallback] = useState<boolean>(false)

  // Check-in state
  const [checkInSubmitting, setCheckInSubmitting] = useState<boolean>(false)
  const [checkInFeedback, setCheckInFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  // Report state
  const [claimType, setClaimType] = useState<ClaimType>('flooded')
  const [reportText, setReportText] = useState<string>('')
  const [reportSubmitting, setReportSubmitting] = useState<boolean>(false)
  const [reportFeedback, setReportFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  const t = translations[language]

  // Check backend health / mode on mount
  useEffect(() => {
    let isCancelled = false
    getHealth()
      .then((h) => {
        if (!isCancelled) setBackendHealth(h)
      })
      .catch(() => {
        if (!isCancelled) setBackendHealth(null)
      })
    return () => {
      isCancelled = true
    }
  }, [])

  useEffect(() => {
    let isCancelled = false
    getCurrentLocation()
      .then((loc) => {
        if (!isCancelled) {
          setUserLocation(loc)
          setLocationError(null)
        }
      })
      .catch((err: Error) => {
        if (!isCancelled) {
          setUserLocation(null)
          setLocationError(err.message)
          setStateData(fallbackState)
          setIsFallback(true)
          setLoading(false)
        }
      })

    return () => {
      isCancelled = true
    }
  }, [])

  const retryLocation = () => {
    setLoading(true)
    setLocationError(null)
    getCurrentLocation()
      .then((loc) => {
        setUserLocation(loc)
        setLocationError(null)
      })
      .catch((err: Error) => {
        setUserLocation(null)
        setLocationError(err.message)
        setStateData(fallbackState)
        setIsFallback(true)
        setLoading(false)
      })
  }

  const fetchDashboardState = useCallback(async (lang: Language, coords: { lat: number; lng: number }) => {
    setLoading(true)
    try {
      const data = await getState(coords.lat, coords.lng, lang)
      setStateData(data)
      setError(null)
      setIsFallback(false)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to connect to StreetVerism safety service'
      setError(msg)
      setStateData(fallbackState)
      setIsFallback(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!userLocation) return

    let isCancelled = false
    
    Promise.resolve().then(() => {
      if (!isCancelled) setLoading(true)
    })

    getState(userLocation.lat, userLocation.lng, language)
      .then((data) => {
        if (!isCancelled) {
          setStateData(data)
          setError(null)
          setIsFallback(false)
        }
      })
      .catch((err: unknown) => {
        if (!isCancelled) {
          const msg = err instanceof Error ? err.message : 'Failed to connect to StreetVerism safety service'
          setError(msg)
          setStateData(fallbackState)
          setIsFallback(true)
        }
      })
      .finally(() => {
        if (!isCancelled) {
          setLoading(false)
        }
      })

    return () => {
      isCancelled = true
    }
  }, [language, userLocation])

  const handleCheckIn = async (state: CheckInState) => {
    if (checkInSubmitting || !userLocation) return
    setCheckInSubmitting(true)
    setCheckInFeedback(null)

    try {
      const deviceId = getDeviceId()
      
      const response = await createCheckIn({
        device_id: deviceId,
        lat: userLocation.lat,
        lng: userLocation.lng,
        state,
        language,
        group_size: 1,
      })

      if (response && response.id) {
        setCheckInFeedback({
          type: 'success',
          message: `Check-in logged successfully (ID: ${response.id}, Time: ${new Date(response.recorded_at).toLocaleTimeString()}).`,
        })
      } else {
        setCheckInFeedback({
          type: 'error',
          message: 'Check-in was not accepted by backend.',
        })
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Check-in submission failed.'
      setCheckInFeedback({
        type: 'error',
        message: msg,
      })
    } finally {
      setCheckInSubmitting(false)
    }
  }

  const handleReportSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (reportSubmitting || !userLocation) return

    setReportSubmitting(true)
    setReportFeedback(null)

    try {
      const deviceId = getDeviceId()

      const response = await createReport({
        device_id: deviceId,
        lat: userLocation.lat,
        lng: userLocation.lng,
        claim: claimType,
        text: reportText.trim() || undefined,
      })

      if (response && response.accepted) {
        setReportFeedback({
          type: 'success',
          message: `Report recorded for cell ${response.cell} (Status: ${response.status}). Pending corroboration.`,
        })
        setReportText('')
      } else {
        setReportFeedback({
          type: 'error',
          message: 'Report submission was rejected by server.',
        })
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Report submission failed.'
      setReportFeedback({
        type: 'error',
        message: msg,
      })
    } finally {
      setReportSubmitting(false)
    }
  }

  const activeState = stateData ?? fallbackState
  const statusInfo = statusDisplayLabels[activeState.status] ?? {
    label: activeState.status.toUpperCase(),
    description: 'Current area hazard evaluation.',
  }

  const scrollToSection = (id: string) => {
    setActiveTab(id)
    setMobileMenuOpen(false)
    const element = document.getElementById(id)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' })
    }
  }

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

      {/* Sticky Dark Navy Sidebar */}
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
            <span>Dashboard</span>
          </button>
          <button 
            className={`nav-item ${activeTab === 'map-section' ? 'active' : ''}`}
            onClick={() => scrollToSection('map-section')}
          >
            <span className="nav-icon">🗺️</span>
            <span>Safety Map</span>
          </button>
          <button 
            className={`nav-item ${activeTab === 'shelters-section' ? 'active' : ''}`}
            onClick={() => scrollToSection('shelters-section')}
          >
            <span className="nav-icon">⌖</span>
            <span>Nearby Shelters</span>
          </button>
          <button 
            className={`nav-item ${activeTab === 'report-section' ? 'active' : ''}`}
            onClick={() => scrollToSection('report-section')}
          >
            <span className="nav-icon">📢</span>
            <span>Report Incident</span>
          </button>
          <button 
            className={`nav-item ${activeTab === 'checkin-section' ? 'active' : ''}`}
            onClick={() => scrollToSection('checkin-section')}
          >
            <span className="nav-icon">✓</span>
            <span>Safety Check-in</span>
          </button>
          <button 
            className={`nav-item ${activeTab === 'lang-section' ? 'active' : ''}`}
            onClick={() => scrollToSection('lang-section')}
          >
            <span className="nav-icon">🌐</span>
            <span>Language Settings</span>
          </button>
        </nav>

        <div className="sidebar-footer">
          <div><strong>StreetVerism Tourist Portal</strong></div>
          <div>Crisis Action &amp; Safety Network</div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content" id="dashboard">
        <header className="header-bar">
          <div className="header-title-group">
            <h1>Tourist Safety Dashboard</h1>
            <p className="header-subtitle">
              {isFallback 
                ? 'Backend API offline — displaying offline demo/fallback state.' 
                : activeState.is_replay || backendHealth?.is_replay || backendHealth?.mode === 'replay'
                  ? 'Historical scenario replay active — not live emergency information.' 
                  : backendHealth?.mode === 'mock'
                    ? 'Backend running in MOCK mode — demo data, not verified emergency information.'
                    : 'Connected to live StreetVerism safety network.'}
            </p>
          </div>

          <div className="badge-group">
            {isFallback ? (
              <span className="mode-badge fallback-badge">OFFLINE · DEMO FALLBACK</span>
            ) : activeState.is_replay || backendHealth?.is_replay || backendHealth?.mode === 'replay' ? (
              <span className="mode-badge">REPLAY SCENARIO</span>
            ) : backendHealth?.mode === 'mock' ? (
              <span className="mode-badge" style={{ background: '#f59e0b', color: '#071827' }}>MOCK DATA (DEMO)</span>
            ) : backendHealth?.mode === 'live' ? (
              <span className="mode-badge live-badge">LIVE API</span>
            ) : (
              <span className="mode-badge" style={{ background: '#64748b', color: '#fff' }}>UNKNOWN MODE</span>
            )}
          </div>
        </header>

        {/* Global Error & Location Notices */}
        {locationError && (
          <div className="dark-error-banner" role="alert">
            <div>
              <strong>📍 Location Access Required:</strong> {locationError} Please enable browser location permissions to receive location-specific safety state and enable submissions.
            </div>
            <button className="retry-button" onClick={retryLocation}>
              Enable Location
            </button>
          </div>
        )}

        {error && (
          <div className="dark-error-banner" role="alert">
            <div>
              <strong>⚠️ Connection Warning:</strong> {error}. Showing offline demo fallback state.
            </div>
            <button 
              className="retry-button" 
              onClick={() => {
                if (userLocation) void fetchDashboardState(language, userLocation)
                else retryLocation()
              }}
              disabled={loading}
            >
              {loading ? 'Retrying...' : 'Retry Connection'}
            </button>
          </div>
        )}

        {loading && (
          <div className="loading-indicator" role="status">
            Updating safety network status for H3 cell evaluation...
          </div>
        )}

        {/* Compact Summary Cards Row */}
        <div className="summary-cards-grid">
          <div className="summary-card">
            <div className="card-label">Current Hazard Status</div>
            <div className="card-value" style={{ color: activeState.status === 'official_hazard' ? '#f87171' : '#4ade80' }}>
              {statusInfo.label}
            </div>
            <div className="card-subtext">Cell: {activeState.cell}</div>
          </div>

          <div className="summary-card">
            <div className="card-label">Posterior Hazard</div>
            <div className="card-value" style={{ color: '#d7f34a' }}>
              {Math.round(activeState.p_hazard * 100)}%
            </div>
            <div className="card-subtext">Bayesian Risk Estimate</div>
          </div>

          <div className="summary-card">
            <div className="card-label">Nearby Open Shelters</div>
            <div className="card-value">
              {userLocation ? activeState.nearest_shelters.filter(s => s.open).length : '—'}
            </div>
            <div className="card-subtext">
              {userLocation ? `${activeState.nearest_shelters.length} Total Nearby` : 'Location Required'}
            </div>
          </div>

          <div className="summary-card">
            <div className="card-label">Active Alerts</div>
            <div className="card-value">
              {activeState.alerts.length}
            </div>
            <div className="card-subtext">Official Advisories</div>
          </div>
        </div>

        {/* Main Interactive Grid: Map & Hazard Info */}
        <div className="dashboard-grid" id="map-section">
          {/* Central Dark Map Canvas Panel */}
          <div className="map-panel">
            <div className="panel-header">
              <div className="panel-title-group">
                <span className="panel-title-icon">🗺️</span>
                <h2>Spatial Hazard Map (H3 Resolution 8)</h2>
              </div>
              <span className="map-chip">
                {userLocation ? `Lat: ${userLocation.lat.toFixed(4)}, Lng: ${userLocation.lng.toFixed(4)}` : 'Location Disabled'}
              </span>
            </div>

            <MapView
              userLocation={userLocation}
              shelters={activeState.nearest_shelters}
              cell={activeState.cell}
              statusLabel={statusInfo.label}
              isReplay={activeState.is_replay || backendHealth?.is_replay || backendHealth?.mode === 'replay'}
              isFallback={isFallback}
              backendMode={backendHealth?.mode}
            />
            
            <p className="notice-box">
              ⚠️ Map visualization displays H3 cell resolution 8 boundary evaluations derived from current backend state. Replay/demo markers are strictly non-authoritative.
            </p>
          </div>

          {/* Right Column: Hazard Info & Language Settings */}
          <div className="side-panels-column">
            {/* Hazard Details Panel */}
            <div className="info-card">
              <div className="status-header-box">
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 750, textTransform: 'uppercase' }}>Hazard Level</div>
                  <h3 style={{ margin: 0, color: '#fff', fontSize: '1.2rem' }}>{statusInfo.label}</h3>
                </div>
                <span className={`status-badge-tag status-${activeState.status}`}>
                  {activeState.status}
                </span>
              </div>

              <p style={{ fontSize: '0.88rem', color: '#cbd5e1', lineHeight: 1.5, margin: '0 0 14px 0' }}>
                {statusInfo.description}
              </p>

              <div style={{ fontSize: '0.8rem', fontWeight: 750, color: '#94a3b8', textTransform: 'uppercase' }}>
                Bayesian Evidence Components
              </div>

              <div className="evidence-list">
                {activeState.evidence.length > 0 ? (
                  activeState.evidence.map((ev, idx) => (
                    <div key={idx} className="evidence-item">
                      <div className="evidence-type">{ev.type} Evidence</div>
                      <div style={{ color: '#cbd5e1' }}>{ev.summary}</div>
                      <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '4px' }}>
                        Age: {ev.age_s}s · Weight: {ev.weight}
                      </div>
                    </div>
                  ))
                ) : (
                  <div style={{ fontSize: '0.85rem', color: '#64748b' }}>No active evidence sources.</div>
                )}
              </div>
            </div>

            {/* Language Selection Card */}
            <div className="info-card" id="lang-section">
              <h3 style={{ margin: '0 0 10px 0', fontSize: '1.05rem', color: '#fff' }}>🌐 Language / Language Selection</h3>
              <p style={{ fontSize: '0.82rem', color: '#94a3b8', margin: '0 0 14px 0' }}>
                Select preferred language for localized crisis instructions.
              </p>
              
              <select 
                className="dark-select"
                value={language} 
                onChange={(event) => setLanguage(event.target.value as Language)}
                disabled={loading}
              >
                <option value="en">English (Verified)</option>
                <option value="hi">हिन्दी (Verified)</option>
                <option value="ta">தமிழ் (Verified)</option>
                <option value="fr">Français · Unreviewed</option>
                <option value="de">Deutsch · Unreviewed</option>
                <option value="ja">日本語 · Unreviewed</option>
              </select>
            </div>
          </div>
        </div>

        {/* Content Section: Safety Instructions & Nearby Shelters */}
        <div className="bottom-grid" id="shelters-section">
          {/* Safety Instructions Panel */}
          <div className="action-card">
            <div className="panel-title-group" style={{ marginBottom: '16px' }}>
              <span className="panel-title-icon">↗</span>
              <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#fff' }}>{t.instructions}</h2>
            </div>

            {activeState.instructions.length > 0 ? (
              <ul className="instruction-list" style={{ paddingLeft: '18px' }}>
                {activeState.instructions.map((inst, idx) => (
                  <li key={inst.key || idx} style={{ marginBottom: '12px' }}>
                    <div>
                      <strong style={{ color: '#f1f5f9' }}>{inst.text}</strong>
                      {inst.reviewed ? (
                        <span style={{ fontSize: '0.75rem', color: '#4ade80', marginLeft: '8px' }}>✓ Verified</span>
                      ) : (
                        <span style={{ fontSize: '0.75rem', color: '#fb923c', marginLeft: '8px' }}>⚠️ Unreviewed Translation</span>
                      )}
                    </div>
                    {!inst.reviewed && inst.original_en && (
                      <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '3px', fontStyle: 'italic' }}>
                        English Original: "{inst.original_en}"
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="card-subtext">No current safety instructions available.</p>
            )}

            <p className="notice-box">
              {isFallback || activeState.is_replay
                ? 'These are scenario replay instructions. Follow local emergency services for real incidents.'
                : 'Follow official guidance and local emergency announcements.'}
            </p>
          </div>

          {/* Nearby Shelters Panel */}
          <div className="action-card">
            <div className="panel-title-group" style={{ marginBottom: '16px' }}>
              <span className="panel-title-icon">⌖</span>
              <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#fff' }}>{t.shelters}</h2>
            </div>

            {userLocation && activeState.nearest_shelters.length > 0 ? (
              activeState.nearest_shelters.map((shelter, idx) => (
                <div key={shelter.id || idx} style={{ padding: '12px 0', borderBottom: '1px solid #1e293b' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 style={{ margin: 0, fontSize: '0.95rem', color: '#ffffff' }}>
                      {shelter.name} {shelter.name_local && `(${shelter.name_local})`}
                    </h3>
                    <span style={{ fontSize: '0.7rem', color: shelter.is_demo ? '#94a3b8' : '#4ade80', background: '#071827', padding: '4px 8px', borderRadius: '6px' }}>
                      {shelter.is_demo ? 'DEMO SHELTER' : 'VERIFIED'}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#94a3b8', marginTop: '4px' }}>
                    {shelter.open ? '🟢 Open for evacuees' : '🔴 Closed'}
                    {shelter.distance_m !== undefined && shelter.distance_m !== null && ` · ${Math.round(shelter.distance_m)}m away`}
                    {shelter.capacity !== undefined && shelter.capacity !== null && ` · Capacity: ${shelter.capacity}`}
                  </div>
                </div>
              ))
            ) : !userLocation ? (
              <p className="card-subtext" style={{ color: '#f87171' }}>📍 Location permission required to calculate nearby shelter distances.</p>
            ) : (
              <p className="card-subtext">No nearby open shelters listed.</p>
            )}

            <p className="notice-box">
              {isFallback || activeState.is_replay
                ? 'Replay shelter data. Verify shelter availability with local authorities during live events.'
                : 'Verify shelter capacity directly with emergency response teams.'}
            </p>
          </div>
        </div>

        {/* Tourist Actions Grid: Safety Check-in & Incident Report */}
        <div className="bottom-grid">
          {/* Safety Check-in Panel */}
          <div className="action-card" id="checkin-section">
            <div className="card-label">YOUR STATUS</div>
            <h2 style={{ margin: '4px 0 8px 0', color: '#fff', fontSize: '1.25rem' }}>Are you safe?</h2>
            <p className="card-subtext">
              Submitting status sends location &amp; device state to StreetVerism safety network triage engine.
            </p>

            {!userLocation && (
              <div className="dark-feedback-error">
                📍 Location permissions required. Please allow browser location access to check in.
              </div>
            )}

            <div className="checkin-btn-group">
              <button 
                className="btn-safe"
                onClick={() => void handleCheckIn('safe')}
                disabled={checkInSubmitting || !userLocation}
              >
                {checkInSubmitting ? 'Submitting...' : `✓ ${t.safe}`}
              </button>
              <button 
                className="btn-help"
                onClick={() => void handleCheckIn('need_help')}
                disabled={checkInSubmitting || !userLocation}
              >
                {checkInSubmitting ? 'Submitting...' : `! ${t.help}`}
              </button>
            </div>

            {checkInFeedback && (
              <div className={checkInFeedback.type === 'error' ? 'dark-feedback-error' : 'dark-feedback-success'} role="status">
                {checkInFeedback.message}
              </div>
            )}

            <p className="notice-box">
              ⚠️ Note: Check-in updates network status only and does not replace contacting local emergency services directly.
            </p>
          </div>

          {/* Incident Reporting Panel */}
          <div className="action-card" id="report-section">
            <div className="card-label">COMMUNITY INCIDENT REPORT</div>
            <h2 style={{ margin: '4px 0 8px 0', color: '#fff', fontSize: '1.25rem' }}>Submit Ground-Truth Observation</h2>
            <p className="card-subtext">
              Reports are marked as unverified until corroborating evidence or H3 cluster consensus is reached.
            </p>

            {!userLocation && (
              <div className="dark-feedback-error">
                📍 Location permissions required. Please allow browser location access to submit a report.
              </div>
            )}

            <form className="report-form-group" onSubmit={(e) => void handleReportSubmit(e)}>
              <div>
                <div className="form-label">Ground Claim</div>
                <select
                  className="dark-select"
                  value={claimType}
                  onChange={(e) => setClaimType(e.target.value as ClaimType)}
                  disabled={reportSubmitting || !userLocation}
                >
                  <option value="flooded">Flooded Area</option>
                  <option value="blocked">Blocked Route</option>
                  <option value="safe">Clear / Safe Area</option>
                </select>
              </div>

              <div>
                <div className="form-label">Optional Description</div>
                <textarea
                  className="dark-textarea"
                  rows={3}
                  placeholder="Describe the condition or hazard observed (optional, max 500 chars)..."
                  value={reportText}
                  onChange={(e) => setReportText(e.target.value)}
                  disabled={reportSubmitting || !userLocation}
                  maxLength={500}
                />
              </div>

              <button 
                type="submit" 
                className="btn-submit"
                disabled={reportSubmitting || !userLocation}
              >
                {reportSubmitting ? 'Submitting Report...' : 'Submit Observation'}
              </button>

              {reportFeedback && (
                <div className={reportFeedback.type === 'error' ? 'dark-feedback-error' : 'dark-feedback-success'} role="status">
                  {reportFeedback.message}
                </div>
              )}
            </form>
          </div>
        </div>

        {/* Dashboard Footer */}
        <footer style={{ marginTop: '40px', padding: '20px 0', borderTop: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', color: '#64748b', fontSize: '0.78rem' }}>
          <div>STREETVERISM · TOURIST CRISIS NETWORK</div>
          <div>
            {isFallback 
              ? 'Offline demo fallback · Not an official emergency service' 
              : activeState.is_replay 
                ? 'Scenario replay active · Not an official emergency service' 
                : 'Live network state · StreetVerism tourist portal'}
          </div>
        </footer>
      </main>
    </div>
  )
}

export default App