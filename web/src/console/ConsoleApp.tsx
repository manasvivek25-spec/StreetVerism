import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './Console.css';
import {
  expireAlert,
  getActiveAlerts,
  getConsoleCheckins,
  getEnglishTemplates,
  getScenarioStatus,
  getStoredAuthorityKey,
  patchCheckinHandled,
  publishAlert,
  resetScenario,
  seekScenario,
  setStoredAuthorityKey,
  startOrResumeScenario,
  type CheckinItem,
  type CheckinListResponse,
  type ConsoleAlert,
  type PublishAlertPayload,
  type ScenarioStatusResponse,
} from './api';

const PRESET_ALERT_ZONES = [
  {
    id: 'adyar',
    name: 'Adyar Flood Basin (Zone 1)',
    polygon: [
      [
        [80.21, 13.002],
        [80.245, 13.002],
        [80.245, 13.03],
        [80.21, 13.03],
        [80.21, 13.002],
      ],
    ],
  },
  {
    id: 'velachery',
    name: 'Velachery Emergency Corridor (Zone 2)',
    polygon: [
      [
        [80.21, 12.97],
        [80.23, 12.97],
        [80.23, 12.995],
        [80.21, 12.995],
        [80.21, 12.97],
      ],
    ],
  },
  {
    id: 'mylapore',
    name: 'Mylapore Coastal Sector (Zone 3)',
    polygon: [
      [
        [80.25, 13.02],
        [80.28, 13.02],
        [80.28, 13.05],
        [80.25, 13.05],
        [80.25, 13.02],
      ],
    ],
  },
  {
    id: 'saidapet',
    name: 'Saidapet Riverbank Sector (Zone 4)',
    polygon: [
      [
        [80.215, 13.01],
        [80.235, 13.01],
        [80.235, 13.03],
        [80.215, 13.03],
        [80.215, 13.01],
      ],
    ],
  },
];

const PRESET_SHELTERS = [
  { id: 'sh_chennai_01', name: 'Demo Relief Center - Velachery' },
  { id: 'sh_chennai_02', name: 'Demo Relief Camp - Mylapore' },
  { id: 'sh_chennai_03', name: 'Demo Cyclone Center - Saidapet' },
  { id: 'sh_chennai_04', name: 'Demo Relief Hall - Guindy' },
];

export const ConsoleApp: React.FC = () => {
  const [authorityKey, setAuthorityKey] = useState<string>(getStoredAuthorityKey());
  const [inputKey, setInputKey] = useState<string>('');
  const [authError, setAuthError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<'checkins' | 'alerts' | 'publish' | 'scenario'>('checkins');

  // Check-ins state
  const [checkinsData, setCheckinsData] = useState<CheckinListResponse | null>(null);
  const [checkinsLoading, setCheckinsLoading] = useState<boolean>(false);
  const [checkinActionId, setCheckinActionId] = useState<string | null>(null);

  // Active alerts state
  const [alerts, setAlerts] = useState<ConsoleAlert[]>([]);
  const [alertsLoading, setAlertsLoading] = useState<boolean>(false);

  // Publish form state
  const [templates, setTemplates] = useState<Record<string, string>>({});
  const [pubHazard, setPubHazard] = useState<string>('flood');
  const [pubSeverity, setPubSeverity] = useState<string>('severe');
  const [pubUrgency, setPubUrgency] = useState<string>('immediate');
  const [pubCertainty, setPubCertainty] = useState<string>('observed');
  const [pubZoneId, setPubZoneId] = useState<string>('adyar');
  const [pubSelectedKeys, setPubSelectedKeys] = useState<string[]>(['MOVE_TO_HIGHER_GROUND', 'AVOID_FLOODED_ROADS']);
  const [pubShelterId, setPubShelterId] = useState<string>('sh_chennai_03');
  const [pubHours, setPubHours] = useState<number>(12);
  const [pubSubmitting, setPubSubmitting] = useState<boolean>(false);
  const [pubFeedback, setPubFeedback] = useState<{ type: 'success' | 'error'; message: string; is409?: boolean } | null>(null);

  // Scenario status state
  const [scenario, setScenario] = useState<ScenarioStatusResponse | null>(null);
  const [scenarioActioning, setScenarioActioning] = useState<boolean>(false);

  // Small Leaflet Map for check-ins
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const mapMarkersRef = useRef<L.LayerGroup | null>(null);

  // Load templates on mount
  useEffect(() => {
    getEnglishTemplates()
      .then((res) => {
        if (res && res.templates) setTemplates(res.templates);
      })
      .catch(() => {
        // Fallback common template keys
        setTemplates({
          MOVE_TO_HIGHER_GROUND: 'Move to higher ground immediately. Do not wait.',
          AVOID_FLOODED_ROADS: 'Avoid flooded roads and underpasses.',
          EVACUATE_TO_SHELTER: 'Evacuate to designated emergency shelter: {shelter}.',
          BOIL_WATER: 'Boil drinking water for at least 1 minute before consumption.',
          SHELTER_OPEN: 'Emergency shelter open with power and medical supplies: {shelter}.',
          POWER_OUTAGE_EXPECTED: 'Power outage expected. Conserve phone battery and emergency lighting.',
        });
      });
  }, []);

  // Poll scenario status every 5 seconds
  useEffect(() => {
    let isCancelled = false;
    const fetchStatus = () => {
      getScenarioStatus()
        .then((s) => {
          if (!isCancelled) setScenario(s);
        })
        .catch(() => {});
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => {
      isCancelled = true;
      clearInterval(interval);
    };
  }, []);

  // Poll check-ins every 10 seconds if authenticated
  useEffect(() => {
    if (!authorityKey) return;
    let isCancelled = false;

    const loadCheckins = () => {
      setCheckinsLoading(true);
      getConsoleCheckins(authorityKey)
        .then((data) => {
          if (!isCancelled) {
            setCheckinsData(data);
            setAuthError(null);
          }
        })
        .catch((err: any) => {
          if (!isCancelled) {
            if (err.status === 403) {
              setAuthError('Invalid Authority Key. Access denied.');
              setAuthorityKey('');
              setStoredAuthorityKey('');
            }
          }
        })
        .finally(() => {
          if (!isCancelled) setCheckinsLoading(false);
        });
    };

    loadCheckins();
    const interval = setInterval(loadCheckins, 10000);
    return () => {
      isCancelled = true;
      clearInterval(interval);
    };
  }, [authorityKey]);

  // Load active alerts when alert tab is active
  useEffect(() => {
    if (!authorityKey || activeTab !== 'alerts') return;
    let isCancelled = false;
    Promise.resolve().then(() => {
      if (!isCancelled) setAlertsLoading(true);
    });
    getActiveAlerts(authorityKey)
      .then((res) => {
        if (!isCancelled) setAlerts(res.alerts || []);
      })
      .catch(() => {})
      .finally(() => {
        if (!isCancelled) setAlertsLoading(false);
      });
    return () => {
      isCancelled = true;
    };
  }, [authorityKey, activeTab]);

  // Handle Login
  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputKey.trim()) return;
    setAuthError(null);
    setCheckinsLoading(true);

    getConsoleCheckins(inputKey.trim())
      .then((data) => {
        setAuthorityKey(inputKey.trim());
        setStoredAuthorityKey(inputKey.trim());
        setCheckinsData(data);
        setInputKey('');
      })
      .catch((err: any) => {
        setAuthError(err.message || 'Authentication failed. Please verify your AUTHORITY_KEY.');
      })
      .finally(() => {
        setCheckinsLoading(false);
      });
  };

  const handleLogout = () => {
    setAuthorityKey('');
    setStoredAuthorityKey('');
    setCheckinsData(null);
  };

  // Toggle Handled on Check-in
  const handleToggleHandled = async (item: CheckinItem) => {
    if (checkinActionId) return;
    setCheckinActionId(item.id);
    try {
      const updated = await patchCheckinHandled(item.id, !item.handled, authorityKey);
      if (checkinsData) {
        setCheckinsData({
          ...checkinsData,
          items: checkinsData.items.map((it) => (it.id === updated.id ? updated : it)),
        });
      }
    } catch (err: any) {
      alert(`Failed to update checkin status: ${err.message}`);
    } finally {
      setCheckinActionId(null);
    }
  };

  // Expire Alert
  const handleExpireAlert = async (alertId: string) => {
    if (!confirm(`Are you sure you want to expire alert ${alertId}?`)) return;
    try {
      await expireAlert(alertId, authorityKey);
      setAlerts((prev) => prev.filter((a) => a.id !== alertId));
    } catch (err: any) {
      alert(`Failed to expire alert: ${err.message}`);
    }
  };

  // Submit New Alert
  const handlePublishSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (pubSubmitting || pubSelectedKeys.length === 0) return;
    setPubSubmitting(true);
    setPubFeedback(null);

    const zone = PRESET_ALERT_ZONES.find((z) => z.id === pubZoneId) || PRESET_ALERT_ZONES[0];
    const shelter = PRESET_SHELTERS.find((s) => s.id === pubShelterId);

    const payload: PublishAlertPayload = {
      hazard: pubHazard,
      severity: pubSeverity,
      urgency: pubUrgency,
      certainty: pubCertainty,
      area: {
        type: 'Polygon',
        coordinates: zone.polygon,
      },
      instruction_keys: pubSelectedKeys,
      params: shelter ? { shelter: shelter.name } : {},
      expires_in_hours: pubHours,
    };

    try {
      const res = await publishAlert(payload, authorityKey);
      setPubFeedback({
        type: 'success',
        message: `Alert published successfully (ID: ${res.id}) in ${zone.name}.`,
      });
    } catch (err: any) {
      const is409 = err.status === 409 || String(err.message).includes('replay');
      setPubFeedback({
        type: 'error',
        message: is409
          ? 'Publishing is disabled during replay. Reset the scenario to go live.'
          : `Publish error: ${err.message}`,
        is409,
      });
    } finally {
      setPubSubmitting(false);
    }
  };

  // Scenario Controls
  const handleSeekBookmark = async (bookmark: string) => {
    setScenarioActioning(true);
    try {
      const updated = await seekScenario(bookmark);
      setScenario(updated);
    } catch (err: any) {
      alert(`Seek failed: ${err.message}`);
    } finally {
      setScenarioActioning(false);
    }
  };

  const handleTogglePlayPause = async () => {
    if (!scenario) return;
    setScenarioActioning(true);
    try {
      const newSpeed = scenario.speed > 0 ? 0.0 : 1.0;
      const updated = await startOrResumeScenario(scenario.name || 'michaung_replay', newSpeed);
      setScenario(updated);
    } catch (err: any) {
      alert(`Action failed: ${err.message}`);
    } finally {
      setScenarioActioning(false);
    }
  };

  const handleResetScenario = async () => {
    setScenarioActioning(true);
    try {
      await resetScenario();
      const updated = await getScenarioStatus();
      setScenario(updated);
      alert('Scenario successfully reset to LIVE mode. Live publishing is now enabled.');
    } catch (err: any) {
      alert(`Reset failed: ${err.message}`);
    } finally {
      setScenarioActioning(false);
    }
  };

  // Initialize and update mini Leaflet map for check-ins
  useEffect(() => {
    if (activeTab !== 'checkins' || !mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [13.015, 80.225],
        zoom: 12,
        zoomControl: false,
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap',
        maxZoom: 18,
      }).addTo(map);

      mapMarkersRef.current = L.layerGroup().addTo(map);
      mapInstanceRef.current = map;
    }

    const markersLayer = mapMarkersRef.current;
    if (markersLayer && checkinsData) {
      markersLayer.clearLayers();
      checkinsData.items.forEach((item) => {
        const isHelp = item.state === 'need_help';
        const color = isHelp ? (item.handled ? '#f59e0b' : '#ef4444') : '#10b981';
        const marker = L.circleMarker([item.lat, item.lng], {
          radius: isHelp ? 9 : 6,
          fillColor: color,
          color: '#ffffff',
          weight: 2,
          opacity: 1,
          fillOpacity: 0.9,
        });

        marker.bindPopup(`
          <div style="font-family: sans-serif; font-size: 12px; color: #071827;">
            <strong>Checkin: ${item.id}</strong><br/>
            State: <strong>${item.state === 'need_help' ? '🚨 NEED HELP' : '✓ SAFE'}</strong><br/>
            Status: ${item.handled ? 'Handled' : 'UNHANDLED'}<br/>
            Lang: ${item.language.toUpperCase()} · Group: ${item.group_size}<br/>
            ${item.note ? `Note: "${item.note}"<br/>` : ''}
            Time: ${new Date(item.created_at).toLocaleTimeString()}
          </div>
        `);
        markersLayer.addLayer(marker);
      });
    }
  }, [activeTab, checkinsData]);

  // Compute Checkin metrics
  const items = checkinsData?.items || [];
  const needHelpItems = items.filter((i) => i.state === 'need_help');
  const safeItems = items.filter((i) => i.state === 'safe');
  const unhandledHelpCount = needHelpItems.filter((i) => !i.handled).length;

  const langCounts: Record<string, number> = {};
  items.forEach((i) => {
    langCounts[i.language] = (langCounts[i.language] || 0) + 1;
  });

  const sortedCheckins = [...items].sort((a, b) => {
    // need_help unhandled first, then need_help handled, then safe
    if (a.state === 'need_help' && b.state !== 'need_help') return -1;
    if (a.state !== 'need_help' && b.state === 'need_help') return 1;
    if (a.state === 'need_help' && b.state === 'need_help') {
      if (!a.handled && b.handled) return -1;
      if (a.handled && !b.handled) return 1;
    }
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  // Render Gate if not authenticated
  if (!authorityKey) {
    return (
      <div className="console-root">
        <header className="console-header">
          <div className="console-title-group">
            <span className="console-badge-icon">🏛️</span>
            <div>
              <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#fff' }}>StreetVerism Authority Console</h2>
              <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Emergency Operations &amp; Incident Dispatch</div>
            </div>
          </div>
          <a href="/" className="console-tab-btn">
            Tourist App ↗
          </a>
        </header>

        <main className="console-container">
          <div className="gate-card">
            <span style={{ fontSize: '2.5rem' }}>🔐</span>
            <h2 style={{ margin: '14px 0 6px 0', color: '#fff' }}>Operator Authentication</h2>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: 0 }}>
              Enter the administrative <code>AUTHORITY_KEY</code> to access the dispatch console and triage dashboard.
            </p>

            <form onSubmit={handleLogin}>
              <input
                type="password"
                className="gate-input"
                placeholder="Enter Authority Secret Key..."
                value={inputKey}
                onChange={(e) => setInputKey(e.target.value)}
                autoFocus
              />
              <button
                type="submit"
                className="btn-submit-alert"
                style={{ width: '100%' }}
                disabled={checkinsLoading}
              >
                {checkinsLoading ? 'Authenticating...' : 'Unlock Console'}
              </button>
            </form>

            {authError && (
              <div style={{ marginTop: '16px', color: '#f87171', fontSize: '0.85rem' }}>
                ⚠️ {authError}
              </div>
            )}
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="console-root">
      {/* Header Bar */}
      <header className="console-header">
        <div className="console-title-group">
          <span className="console-badge-icon">🏛️</span>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#fff' }}>StreetVerism Authority Console</h2>
            <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
              Mode: {scenario?.is_replay ? 'REPLAY SIMULATION' : 'LIVE DISPATCH'} · Polling active
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <nav className="console-nav-tabs">
          <button
            className={`console-tab-btn ${activeTab === 'checkins' ? 'active' : ''}`}
            onClick={() => setActiveTab('checkins')}
          >
            <span>🚨 Check-in Triage</span>
            {unhandledHelpCount > 0 && (
              <span style={{ background: '#ef4444', color: '#fff', padding: '2px 6px', borderRadius: '10px', fontSize: '0.75rem', fontWeight: 800 }}>
                {unhandledHelpCount}
              </span>
            )}
          </button>
          <button
            className={`console-tab-btn ${activeTab === 'alerts' ? 'active' : ''}`}
            onClick={() => setActiveTab('alerts')}
          >
            <span>📢 Active Alerts</span>
          </button>
          <button
            className={`console-tab-btn ${activeTab === 'publish' ? 'active' : ''}`}
            onClick={() => setActiveTab('publish')}
          >
            <span>📝 Publish Alert</span>
          </button>
          <button
            className={`console-tab-btn ${activeTab === 'scenario' ? 'active' : ''}`}
            onClick={() => setActiveTab('scenario')}
          >
            <span>⏱️ Scenario &amp; Demo</span>
          </button>
          <a href="/" className="console-tab-btn">
            Tourist App ↗
          </a>
          <button
            className="console-tab-btn"
            style={{ color: '#f87171' }}
            onClick={handleLogout}
            title="Log out and clear session key"
          >
            Lock 🔒
          </button>
        </nav>
      </header>

      {/* Main Content Area */}
      <main className="console-container">
        {/* Replay Banner Warning */}
        {scenario?.is_replay && (
          <div
            style={{
              background: '#4c1d95',
              border: '1px solid #7c3aed',
              borderRadius: '10px',
              padding: '10px 16px',
              marginBottom: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px',
              fontSize: '0.85rem',
            }}
          >
            <div>
              <strong>REPLAY: illustrative reconstruction.</strong> Current sim time:{' '}
              <code>{scenario.current_time || 'Replay active'}</code> (offset: {scenario.elapsed_s}s). Alert publishing is disabled in replay.
            </div>
            <button
              className="scenario-btn danger"
              onClick={handleResetScenario}
              disabled={scenarioActioning}
            >
              Reset to Live Mode
            </button>
          </div>
        )}

        {/* TAB 1: CHECK-IN TRIAGE DASHBOARD */}
        {activeTab === 'checkins' && (
          <div>
            {/* Metrics Row */}
            <div className="console-metrics-grid">
              <div className="console-metric-card" style={{ borderLeft: '4px solid #ef4444' }}>
                <div style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 700 }}>UNHANDLED RESCUE REQUESTS</div>
                <div className="console-metric-val" style={{ color: '#f87171' }}>
                  {unhandledHelpCount}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Prioritized for field response</div>
              </div>

              <div className="console-metric-card" style={{ borderLeft: '4px solid #f59e0b' }}>
                <div style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 700 }}>TOTAL "NEED HELP"</div>
                <div className="console-metric-val" style={{ color: '#fbbf24' }}>
                  {needHelpItems.length}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                  {needHelpItems.length - unhandledHelpCount} Marked Handled
                </div>
              </div>

              <div className="console-metric-card" style={{ borderLeft: '4px solid #10b981' }}>
                <div style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 700 }}>REPORTED SAFE</div>
                <div className="console-metric-val" style={{ color: '#4ade80' }}>
                  {safeItems.length}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Accounted for safe evacuees</div>
              </div>

              <div className="console-metric-card">
                <div style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 700 }}>LANGUAGE BREAKDOWN</div>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '8px' }}>
                  {Object.entries(langCounts).map(([lang, cnt]) => (
                    <span
                      key={lang}
                      style={{
                        background: '#071827',
                        border: '1px solid #334155',
                        padding: '3px 8px',
                        borderRadius: '6px',
                        fontSize: '0.78rem',
                      }}
                    >
                      <strong>{lang.toUpperCase()}</strong>: {cnt}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Check-ins Leaflet Map & Table Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 340px', gap: '20px', marginBottom: '24px' }}>
              {/* Triage Table */}
              <div className="console-panel" style={{ margin: 0 }}>
                <div className="console-panel-header">
                  <h3 style={{ margin: 0, color: '#fff', fontSize: '1.1rem' }}>
                    Incident Triage Queue ({items.length} total)
                  </h3>
                  <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                    {checkinsLoading ? 'Refreshing queue...' : 'Auto-polling every 10s'}
                  </span>
                </div>

                <div style={{ overflowX: 'auto' }}>
                  <table className="console-table">
                    <thead>
                      <tr>
                        <th>Status</th>
                        <th>ID</th>
                        <th>Coordinates</th>
                        <th>Language</th>
                        <th>Group</th>
                        <th>Note</th>
                        <th>Time (UTC)</th>
                        <th>Dispatch Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedCheckins.length === 0 ? (
                        <tr>
                          <td colSpan={8} style={{ textAlign: 'center', color: '#64748b', padding: '24px' }}>
                            No tourist check-ins recorded yet.
                          </td>
                        </tr>
                      ) : (
                        sortedCheckins.map((chk) => {
                          const isHelp = chk.state === 'need_help';
                          return (
                            <tr key={chk.id} className={isHelp && !chk.handled ? 'row-need-help' : ''}>
                              <td>
                                {isHelp ? (
                                  <span style={{ color: chk.handled ? '#fbbf24' : '#ef4444', fontWeight: 800 }}>
                                    🚨 NEED HELP
                                  </span>
                                ) : (
                                  <span style={{ color: '#4ade80', fontWeight: 700 }}>✓ SAFE</span>
                                )}
                              </td>
                              <td><code>{chk.id}</code></td>
                              <td>{chk.lat.toFixed(4)}, {chk.lng.toFixed(4)}</td>
                              <td><span style={{ textTransform: 'uppercase', fontWeight: 700 }}>{chk.language}</span></td>
                              <td>{chk.group_size} pax</td>
                              <td style={{ maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {chk.note || '—'}
                              </td>
                              <td style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                                {new Date(chk.created_at).toLocaleTimeString()}
                              </td>
                              <td>
                                <button
                                  className={`btn-toggle-handled ${chk.handled ? 'handled' : 'unhandled'}`}
                                  onClick={() => handleToggleHandled(chk)}
                                  disabled={checkinActionId === chk.id}
                                >
                                  {checkinActionId === chk.id
                                    ? 'Updating...'
                                    : chk.handled
                                      ? '✓ Handled'
                                      : 'Mark Handled'}
                                </button>
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Small Map Panel */}
              <div className="console-panel" style={{ margin: 0, display: 'flex', flexDirection: 'column' }}>
                <div className="console-panel-header">
                  <h3 style={{ margin: 0, color: '#fff', fontSize: '1rem' }}>Spatial Distribution</h3>
                </div>
                <div
                  ref={mapContainerRef}
                  style={{ width: '100%', height: '360px', borderRadius: '8px', overflow: 'hidden', background: '#050e18' }}
                />
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '10px' }}>
                  Red: Unhandled Need Help · Amber: Handled Help · Green: Safe
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: ACTIVE ALERTS */}
        {activeTab === 'alerts' && (
          <div className="console-panel">
            <div className="console-panel-header">
              <h3 style={{ margin: 0, color: '#fff', fontSize: '1.1rem' }}>Active Disaster Advisories</h3>
              <button
                className="console-tab-btn"
                onClick={() => {
                  setAlertsLoading(true);
                  getActiveAlerts(authorityKey)
                    .then((res) => setAlerts(res.alerts || []))
                    .finally(() => setAlertsLoading(false));
                }}
                disabled={alertsLoading}
              >
                {alertsLoading ? 'Refreshing...' : '🔄 Refresh Alerts'}
              </button>
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table className="console-table">
                <thead>
                  <tr>
                    <th>Alert ID</th>
                    <th>Hazard</th>
                    <th>Severity</th>
                    <th>Urgency</th>
                    <th>Instruction Keys</th>
                    <th>Sent At</th>
                    <th>Expires At</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.length === 0 ? (
                    <tr>
                      <td colSpan={8} style={{ textAlign: 'center', color: '#64748b', padding: '24px' }}>
                        No active alerts currently in circulation.
                      </td>
                    </tr>
                  ) : (
                    alerts.map((alt) => (
                      <tr key={alt.id}>
                        <td><code>{alt.id}</code></td>
                        <td><strong style={{ textTransform: 'capitalize' }}>{alt.hazard}</strong></td>
                        <td>
                          <span
                            style={{
                              color: alt.severity === 'extreme' ? '#f87171' : alt.severity === 'severe' ? '#fb923c' : '#facc15',
                              fontWeight: 700,
                              textTransform: 'uppercase',
                            }}
                          >
                            {alt.severity}
                          </span>
                        </td>
                        <td><span style={{ textTransform: 'capitalize' }}>{alt.urgency}</span></td>
                        <td>
                          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                            {alt.instruction_keys.map((k) => (
                              <span
                                key={k}
                                style={{
                                  background: '#071827',
                                  border: '1px solid #1e3a5f',
                                  fontSize: '0.72rem',
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                }}
                              >
                                {k}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{new Date(alt.sent_at).toLocaleString()}</td>
                        <td style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{new Date(alt.expires_at).toLocaleString()}</td>
                        <td>
                          <button
                            className="btn-action-danger"
                            onClick={() => handleExpireAlert(alt.id)}
                          >
                            Expire Now
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 3: PUBLISH ALERT */}
        {activeTab === 'publish' && (
          <div className="console-panel" style={{ maxWidth: '800px', margin: '0 auto' }}>
            <div className="console-panel-header">
              <h3 style={{ margin: 0, color: '#fff', fontSize: '1.2rem' }}>Publish Official Emergency Alert</h3>
              <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Broadcasts to all tourists in zone</span>
            </div>

            <form onSubmit={handlePublishSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
                <div className="console-form-group">
                  <label className="console-label">Hazard Category</label>
                  <select
                    className="console-select"
                    value={pubHazard}
                    onChange={(e) => setPubHazard(e.target.value)}
                  >
                    <option value="flood">Flood Hazard</option>
                    <option value="cyclone">Cyclone / Severe Storm</option>
                    <option value="surge">Coastal Surge</option>
                    <option value="infrastructure">Infrastructure Failure</option>
                  </select>
                </div>

                <div className="console-form-group">
                  <label className="console-label">Severity Level</label>
                  <select
                    className="console-select"
                    value={pubSeverity}
                    onChange={(e) => setPubSeverity(e.target.value)}
                  >
                    <option value="extreme">Extreme (Immediate Threat)</option>
                    <option value="severe">Severe (High Threat)</option>
                    <option value="moderate">Moderate</option>
                    <option value="minor">Minor</option>
                  </select>
                </div>

                <div className="console-form-group">
                  <label className="console-label">Urgency</label>
                  <select
                    className="console-select"
                    value={pubUrgency}
                    onChange={(e) => setPubUrgency(e.target.value)}
                  >
                    <option value="immediate">Immediate</option>
                    <option value="expected">Expected</option>
                    <option value="future">Future</option>
                  </select>
                </div>

                <div className="console-form-group">
                  <label className="console-label">Certainty</label>
                  <select
                    className="console-select"
                    value={pubCertainty}
                    onChange={(e) => setPubCertainty(e.target.value)}
                  >
                    <option value="observed">Observed</option>
                    <option value="likely">Likely</option>
                    <option value="possible">Possible</option>
                  </select>
                </div>
              </div>

              <div className="console-form-group">
                <label className="console-label">Target Zone Polygon</label>
                <select
                  className="console-select"
                  value={pubZoneId}
                  onChange={(e) => setPubZoneId(e.target.value)}
                >
                  {PRESET_ALERT_ZONES.map((zone) => (
                    <option key={zone.id} value={zone.id}>
                      {zone.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="console-form-group">
                <label className="console-label">Designated Safe Shelter</label>
                <select
                  className="console-select"
                  value={pubShelterId}
                  onChange={(e) => setPubShelterId(e.target.value)}
                >
                  {PRESET_SHELTERS.map((sh) => (
                    <option key={sh.id} value={sh.id}>
                      {sh.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="console-form-group">
                <label className="console-label">Instruction Keys (Select multiple)</label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '8px', marginTop: '6px' }}>
                  {Object.entries(templates).map(([key, text]) => {
                    const isChecked = pubSelectedKeys.includes(key);
                    return (
                      <label
                        key={key}
                        style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: '8px',
                          background: isChecked ? '#172554' : '#071827',
                          border: `1px solid ${isChecked ? '#3b82f6' : '#1e293b'}`,
                          padding: '8px 10px',
                          borderRadius: '6px',
                          cursor: 'pointer',
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setPubSelectedKeys([...pubSelectedKeys, key]);
                            } else {
                              setPubSelectedKeys(pubSelectedKeys.filter((k) => k !== key));
                            }
                          }}
                          style={{ marginTop: '3px' }}
                        />
                        <div style={{ fontSize: '0.8rem' }}>
                          <strong style={{ color: isChecked ? '#93c5fd' : '#e2e8f0' }}>{key}</strong>
                          <div style={{ color: '#94a3b8', fontSize: '0.75rem', marginTop: '2px' }}>{text}</div>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div className="console-form-group">
                <label className="console-label">Duration (Hours)</label>
                <input
                  type="number"
                  className="console-input"
                  min={1}
                  max={72}
                  value={pubHours}
                  onChange={(e) => setPubHours(parseInt(e.target.value, 10) || 12)}
                />
              </div>

              <button
                type="submit"
                className="btn-submit-alert"
                style={{ width: '100%', marginTop: '10px' }}
                disabled={pubSubmitting || pubSelectedKeys.length === 0}
              >
                {pubSubmitting ? 'Transmitting Alert...' : '🚀 Broadcast Official Alert'}
              </button>
            </form>

            {pubFeedback && (
              <div
                style={{
                  marginTop: '16px',
                  padding: '12px 16px',
                  borderRadius: '8px',
                  background: pubFeedback.type === 'error' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                  border: `1px solid ${pubFeedback.type === 'error' ? '#ef4444' : '#10b981'}`,
                  color: pubFeedback.type === 'error' ? '#fca5a5' : '#86efac',
                  fontSize: '0.88rem',
                }}
              >
                <div>{pubFeedback.message}</div>
                {pubFeedback.is409 && (
                  <button
                    className="scenario-btn danger"
                    style={{ marginTop: '10px' }}
                    onClick={handleResetScenario}
                  >
                    Reset Scenario to Live
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: SCENARIO CONTROL & DEMO */}
        {activeTab === 'scenario' && (
          <div className="console-panel">
            <div className="console-panel-header">
              <h3 style={{ margin: 0, color: '#fff', fontSize: '1.2rem' }}>Replay Scenario Simulation Control</h3>
              <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Historical Cyclone Michaung Reconstruction</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '24px' }}>
              <div className="console-metric-card">
                <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>OPERATING MODE</div>
                <div className="console-metric-val" style={{ color: scenario?.is_replay ? '#c084fc' : '#4ade80' }}>
                  {scenario?.mode?.toUpperCase() || 'LIVE'}
                </div>
              </div>

              <div className="console-metric-card">
                <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>SIMULATION CLOCK</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#ffffff', marginTop: '6px' }}>
                  {scenario?.current_time ? new Date(scenario.current_time).toLocaleString() : 'Real Time'}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '2px' }}>
                  Elapsed: {scenario?.elapsed_s || 0}s (+{Math.round((scenario?.elapsed_s || 0) / 3600)}h)
                </div>
              </div>

              <div className="console-metric-card">
                <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>PLAYBACK STATUS</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#ffffff', marginTop: '6px' }}>
                  {scenario?.is_replay ? (scenario?.speed === 0 ? '⏸️ PAUSED' : `▶️ RUNNING (${scenario?.speed}x)`) : 'LIVE FEED'}
                </div>
              </div>
            </div>

            <h4 style={{ color: '#d7f34a', margin: '0 0 10px 0' }}>⭐ Seek to Key Replay Bookmarks</h4>
            <div className="scenario-bar" style={{ marginBottom: '24px' }}>
              <button
                className="scenario-btn primary"
                onClick={() => handleSeekBookmark('golden_moment')}
                disabled={scenarioActioning}
              >
                ⭐ Golden Moment (+09h30m)
              </button>
              <button
                className="scenario-btn"
                onClick={() => handleSeekBookmark('early_warning')}
                disabled={scenarioActioning}
              >
                Early Warning (+07h30m)
              </button>
              <button
                className="scenario-btn"
                onClick={() => handleSeekBookmark('viral_rumor')}
                disabled={scenarioActioning}
              >
                Viral Rumor (+08h30m)
              </button>
              <button
                className="scenario-btn"
                onClick={() => handleSeekBookmark('all_clear_contradicted')}
                disabled={scenarioActioning}
              >
                All-Clear Contradicted (+11h30m)
              </button>
              <button
                className="scenario-btn"
                onClick={() => handleSeekBookmark('claims_aged_out')}
                disabled={scenarioActioning}
              >
                Claims Aged Out (+17h00m)
              </button>
            </div>

            <h4 style={{ color: '#fff', margin: '0 0 10px 0' }}>Playback &amp; Live Reversion</h4>
            <div className="scenario-bar">
              <button
                className="scenario-btn"
                onClick={handleTogglePlayPause}
                disabled={scenarioActioning || !scenario?.is_replay}
              >
                {scenario?.speed === 0 ? '▶️ Resume Replay' : '⏸️ Pause Replay'}
              </button>
              <button
                className="scenario-btn"
                onClick={() => startOrResumeScenario('michaung_replay', 2.0).then(setScenario)}
                disabled={scenarioActioning || !scenario?.is_replay}
              >
                ⏩ 2x Speed
              </button>
              <button
                className="scenario-btn"
                onClick={() => startOrResumeScenario('michaung_replay', 5.0).then(setScenario)}
                disabled={scenarioActioning || !scenario?.is_replay}
              >
                ⏩ 5x Speed
              </button>
              <button
                className="scenario-btn danger"
                onClick={handleResetScenario}
                disabled={scenarioActioning}
              >
                🔄 Reset Scenario to Live Mode
              </button>
              {!scenario?.is_replay && (
                <button
                  className="scenario-btn primary"
                  onClick={async () => {
                    setScenarioActioning(true);
                    try {
                      await startOrResumeScenario('michaung_replay', 0.0);
                      const updated = await seekScenario('golden_moment');
                      setScenario(updated);
                    } catch (err: any) {
                      alert(`Failed to restart replay: ${err.message}`);
                    } finally {
                      setScenarioActioning(false);
                    }
                  }}
                  disabled={scenarioActioning}
                >
                  ⏮️ Return to Replay (at golden_moment)
                </button>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
