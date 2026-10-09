import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { createCheckIn, createReport, getState } from './api/client'
import type { CheckInState, Language, StateResponse } from './api/types'

const translations: Record<Language, { title: string; subtitle: string; status: string; instructions: string; shelters: string; safe: string; help: string }> = {
  en: { title: 'StreetVerism', subtitle: 'Your local safety companion', status: 'Local hazard status', instructions: 'Safety instructions', shelters: 'Nearby safe zones', safe: "I'm safe", help: 'I need help' },
  hi: { title: 'StreetVerism', subtitle: 'आपका स्थानीय सुरक्षा सहायक', status: 'स्थानीय खतरे की स्थिति', instructions: 'सुरक्षा निर्देश', shelters: 'पास के सुरक्षित स्थान', safe: 'मैं सुरक्षित हूँ', help: 'मुझे मदद चाहिए' },
  ta: { title: 'StreetVerism', subtitle: 'உங்கள் உள்ளூர் பாதுகாப்பு உதவியாளர்', status: 'உள்ளூர் ஆபத்து நிலை', instructions: 'பாதுகாப்பு வழிமுறைகள்', shelters: 'அருகிலுள்ள பாதுகாப்பான இடங்கள்', safe: 'நான் பாதுகாப்பாக இருக்கிறேன்', help: 'எனக்கு உதவி தேவை' },
  fr: { title: 'StreetVerism', subtitle: 'Votre compagnon de sécurité local', status: 'État des risques locaux', instructions: 'Consignes de sécurité', shelters: 'Zones sûres à proximité', safe: 'Je suis en sécurité', help: "J’ai besoin d’aide" },
  de: { title: 'StreetVerism', subtitle: 'Ihr lokaler Sicherheitsbegleiter', status: 'Lokale Gefahrenlage', instructions: 'Sicherheitshinweise', shelters: 'Sichere Orte in der Nähe', safe: 'Ich bin in Sicherheit', help: 'Ich brauche Hilfe' },
  ja: { title: 'StreetVerism', subtitle: '地域の安全をサポート', status: '地域の危険状況', instructions: '安全に関する指示', shelters: '近くの安全な避難場所', safe: '安全です', help: '助けが必要です' },
}

const fallbackState: StateResponse = {
  language: 'en',
  hazard_status: 'UNVERIFIED',
  headline: 'Community flood report',
  summary: 'A report has been received, but it has not been independently confirmed.',
  alerts: [],
  instructions: [
    { id: 'fb-1', step: 1, text: 'Avoid flooded roads and underpasses.' },
    { id: 'fb-2', step: 2, text: 'Never walk or drive through floodwater.' },
    { id: 'fb-3', step: 3, text: 'Follow verified official announcements.' },
    { id: 'fb-4', step: 4, text: 'Keep your phone charged and accessible.' },
  ],
  evidence: [
    { id: 'ev-1', type: 'community_report', source: 'community report' }
  ],
  shelters: [
    {
      id: 'sh-1',
      name: 'Demo Community Shelter',
      address: 'Illustrative location · Availability unverified',
      is_verified: false,
    }
  ],
  is_demo: true
}

function getDeviceId(): string {
  const storageKey = 'streetverism_device_id'
  let id = localStorage.getItem(storageKey)
  if (!id) {
    id = 'dev_' + Math.random().toString(36).substring(2, 11) + Date.now().toString(36)
    localStorage.setItem(storageKey, id)
  }
  return id
}

function getCurrentLocation(): Promise<{ latitude: number; longitude: number }> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Geolocation is not supported by your browser.'))
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        resolve({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
        })
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) {
          reject(new Error('Location permission denied. Please allow location access to submit location-based status.'))
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          reject(new Error('Location information is currently unavailable from your device.'))
        } else if (err.code === err.TIMEOUT) {
          reject(new Error('Location request timed out. Please check your GPS signal and retry.'))
        } else {
          reject(new Error('Unable to retrieve current location: ' + err.message))
        }
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    )
  })
}

function App() {
  const [language, setLanguage] = useState<Language>('en')
  
  const [stateData, setStateData] = useState<StateResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [isFallback, setIsFallback] = useState<boolean>(false)

  // Check-in state
  const [checkInSubmitting, setCheckInSubmitting] = useState<boolean>(false)
  const [checkInFeedback, setCheckInFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  // Report state
  const [claimType, setClaimType] = useState<'flooded' | 'blocked' | 'safe'>('flooded')
  const [reportDescription, setReportDescription] = useState<string>('')
  const [reportSubmitting, setReportSubmitting] = useState<boolean>(false)
  const [reportFeedback, setReportFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  const t = translations[language]

  const fetchDashboardState = useCallback(async (lang: Language) => {
    setLoading(true)
    try {
      const data = await getState(lang)
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
    let isCancelled = false
    Promise.resolve().then(() => {
      if (!isCancelled) setLoading(true)
    })
    getState(language)
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
  }, [language])

  const handleCheckIn = async (status: CheckInState) => {
    if (checkInSubmitting) return
    setCheckInSubmitting(true)
    setCheckInFeedback(null)

    try {
      const location = await getCurrentLocation()
      const deviceId = getDeviceId()
      
      const response = await createCheckIn({
        status,
        state: status,
        device_id: deviceId,
        user_id: deviceId,
        language,
        group_size: 1,
        lat: location.latitude,
        lng: location.longitude,
        location,
      })

      if (response.success !== false) {
        setCheckInFeedback({
          type: 'success',
          message: response.message || `Check-in recorded: ${status === 'SAFE' ? t.safe : t.help}.`,
        })
      } else {
        setCheckInFeedback({
          type: 'error',
          message: response.message || 'Check-in was not accepted by the backend service.',
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
    if (reportSubmitting) return

    if (!reportDescription.trim()) {
      setReportFeedback({
        type: 'error',
        message: 'Please provide a brief description for your community report.',
      })
      return
    }

    setReportSubmitting(true)
    setReportFeedback(null)

    try {
      const location = await getCurrentLocation()
      const deviceId = getDeviceId()

      const response = await createReport({
        claim: claimType,
        claim_type: claimType,
        category: claimType,
        description: reportDescription.trim(),
        text: reportDescription.trim(),
        device_id: deviceId,
        lat: location.latitude,
        lng: location.longitude,
        location,
      })

      if (response.success !== false) {
        setReportFeedback({
          type: 'success',
          message: response.message || `Community report (${claimType}) submitted successfully.`,
        })
        setReportDescription('')
      } else {
        setReportFeedback({
          type: 'error',
          message: response.message || 'Report was not accepted by the backend service.',
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

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#" aria-label="StreetVerism home">
          <span className="brand-icon">S</span>
          <span>{t.title}</span>
        </a>
        <div className="badge-group">
          {!isFallback && activeState.is_demo !== false ? (
            <span className="mode-badge">REPLAY · DEMO API</span>
          ) : isFallback ? (
            <span className="mode-badge fallback-badge">OFFLINE · DEMO FALLBACK</span>
          ) : (
            <span className="mode-badge live-badge">LIVE API</span>
          )}
        </div>
      </header>

      <section className="welcome">
        <p className="eyebrow">TRAVEL SAFETY NETWORK</p>
        <h1>{t.subtitle}</h1>
        <p className="muted">
          {isFallback 
            ? 'Backend API offline — displaying offline demo/fallback state.' 
            : activeState.is_demo !== false 
              ? 'Illustrative reconstruction — not live emergency information.' 
              : 'Connected to live StreetVerism service.'}
        </p>
        <label className="language-picker">
          <span>Language / மொழி / भाषा</span>
          <select 
            value={language} 
            onChange={(event) => setLanguage(event.target.value as Language)}
            disabled={loading}
          >
            <option value="en">English</option>
            <option value="hi">हिन्दी</option>
            <option value="ta">தமிழ்</option>
            <option value="fr">Français · Unreviewed</option>
            <option value="de">Deutsch · Unreviewed</option>
            <option value="ja">日本語 · Unreviewed</option>
          </select>
        </label>
      </section>

      {error && (
        <div className="error-banner" role="alert">
          <div className="error-message">
            <strong>Connection Warning:</strong> {error}. Showing offline demo fallback state.
          </div>
          <button 
            className="retry-button" 
            onClick={() => void fetchDashboardState(language)}
            disabled={loading}
          >
            {loading ? 'Retrying...' : 'Retry Connection'}
          </button>
        </div>
      )}

      {loading && (
        <div className="loading-indicator" role="status">
          Updating safety network status...
        </div>
      )}

      <section className="status-card" aria-labelledby="status-heading">
        <div className="card-heading">
          <span className="status-symbol">!</span>
          <div>
            <p className="eyebrow">CURRENT AREA</p>
            <h2 id="status-heading">{t.status}</h2>
          </div>
          <span className="status-label">{activeState.hazard_status}</span>
        </div>
        <h3>{activeState.headline || 'Community hazard status'}</h3>
        {activeState.summary && <p className="muted">{activeState.summary}</p>}
        {activeState.unverified_claim && (
          <div className="unverified-claim-box">
            <strong>Unverified Crowd Claim:</strong> {activeState.unverified_claim.description}
            {activeState.unverified_claim.confidence_score !== undefined && (
              <span className="confidence-tag"> Confidence: {Math.round(activeState.unverified_claim.confidence_score * 100)}%</span>
            )}
          </div>
        )}
        <div className="status-footer">
          <span>
            Evidence: {activeState.evidence.length > 0 
              ? activeState.evidence.map(e => e.source || e.type).join(', ') 
              : 'community report'}
          </span>
          <span>{isFallback ? 'Offline demo fallback' : activeState.is_demo !== false ? 'Demo API data' : 'Live state data'}</span>
        </div>
      </section>

      <div className="content-grid">
        <section className="panel">
          <div className="panel-title">
            <span className="panel-icon">↗</span>
            <h2>{t.instructions}</h2>
          </div>
          {activeState.instructions.length > 0 ? (
            <ul className="instruction-list">
              {activeState.instructions.map((inst) => (
                <li key={inst.id || inst.step}>{inst.text}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">No current safety instructions available.</p>
          )}
          <p className="notice">
            {isFallback || activeState.is_demo !== false
              ? 'These are general demo instructions. Follow local emergency services for real incidents.'
              : 'Follow official guidance and local emergency announcements.'}
          </p>
        </section>

        <section className="panel">
          <div className="panel-title">
            <span className="panel-icon">⌖</span>
            <h2>{t.shelters}</h2>
          </div>
          {activeState.shelters.length > 0 ? (
            activeState.shelters.map((shelter, idx) => (
              <article key={shelter.id || idx} className="shelter">
                <div className="shelter-pin">{idx + 1}</div>
                <div>
                  <h3>{shelter.name}</h3>
                  <p className="muted">
                    {shelter.address || 'Location details pending'}
                    {shelter.capacity !== undefined && ` · Capacity: ${shelter.occupancy ?? 0}/${shelter.capacity}`}
                  </p>
                  <span className="demo-tag">
                    {shelter.is_verified ? 'VERIFIED SHELTER' : 'DEMO — NOT VERIFIED'}
                  </span>
                </div>
              </article>
            ))
          ) : (
            <p className="muted">No nearby shelters listed.</p>
          )}
          <p className="notice">
            {isFallback || activeState.is_demo !== false
              ? 'No live shelter data is connected yet. Verify shelter availability with local authorities.'
              : 'Verify shelter capacity and access directly with local response teams.'}
          </p>
        </section>
      </div>

      <section className="checkin-panel">
        <div>
          <p className="eyebrow">YOUR STATUS</p>
          <h2>Are you safe?</h2>
          <p className="muted">
            Submitting status sends location &amp; device state to StreetVerism safety network backend.
          </p>
        </div>
        <div className="checkin-actions">
          <button 
            className="safe-button" 
            onClick={() => void handleCheckIn('SAFE')}
            disabled={checkInSubmitting}
          >
            {checkInSubmitting ? 'Submitting...' : `✓ ${t.safe}`}
          </button>
          <button 
            className="help-button" 
            onClick={() => void handleCheckIn('HELP_NEEDED')}
            disabled={checkInSubmitting}
          >
            {checkInSubmitting ? 'Submitting...' : `! ${t.help}`}
          </button>
        </div>
        {checkInFeedback && (
          <p className={`feedback ${checkInFeedback.type === 'error' ? 'feedback-error' : 'feedback-success'}`} role="status">
            {checkInFeedback.message}
          </p>
        )}
        <p className="disclaimer-note">
          ⚠️ Note: Check-in updates network status only and does not replace contacting local emergency services directly.
        </p>
      </section>

      <section className="report-panel">
        <div>
          <p className="eyebrow">COMMUNITY INCIDENT REPORT</p>
          <h2>Submit a Local Claim</h2>
          <p className="muted">
            Community submissions help inform local awareness. Reports are marked as unverified until reviewed.
          </p>
        </div>
        <form className="report-form" onSubmit={(e) => void handleReportSubmit(e)}>
          <div className="form-row">
            <label htmlFor="claimType">Claim Type</label>
            <select
              id="claimType"
              value={claimType}
              onChange={(e) => setClaimType(e.target.value as 'flooded' | 'blocked' | 'safe')}
              disabled={reportSubmitting}
            >
              <option value="flooded">Flooded Area</option>
              <option value="blocked">Blocked Route</option>
              <option value="safe">Clear / Safe Area</option>
            </select>
          </div>

          <div className="form-row">
            <label htmlFor="reportDescription">Description</label>
            <textarea
              id="reportDescription"
              placeholder="Describe the condition or hazard observed..."
              value={reportDescription}
              onChange={(e) => setReportDescription(e.target.value)}
              disabled={reportSubmitting}
            />
          </div>

          <button 
            type="submit" 
            className="submit-button"
            disabled={reportSubmitting}
          >
            {reportSubmitting ? 'Submitting Report...' : 'Submit Community Report'}
          </button>

          {reportFeedback && (
            <p className={`feedback ${reportFeedback.type === 'error' ? 'feedback-error' : 'feedback-success'}`} role="status">
              {reportFeedback.message}
            </p>
          )}
        </form>
      </section>

      <footer>
        <span>STREETVERISM</span>
        <span>
          {isFallback 
            ? 'Offline demo fallback · Not an official emergency service' 
            : activeState.is_demo !== false 
              ? 'Illustrative demo · Not an official emergency service' 
              : 'Live network state · StreetVerism tourist portal'}
        </span>
      </footer>
    </main>
  )
}

export default App