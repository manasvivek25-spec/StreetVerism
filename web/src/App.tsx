import { useState } from 'react'
import './App.css'

type Language = 'en' | 'hi' | 'ta' | 'fr' | 'de' | 'ja'

const translations: Record<Language, { title: string; subtitle: string; status: string; instructions: string; shelters: string; safe: string; help: string }> = {
  en: { title: 'Beacon', subtitle: 'Your local safety companion', status: 'Local hazard status', instructions: 'Safety instructions', shelters: 'Nearby safe zones', safe: "I'm safe", help: 'I need help' },
  hi: { title: 'Beacon', subtitle: 'आपका स्थानीय सुरक्षा सहायक', status: 'स्थानीय खतरे की स्थिति', instructions: 'सुरक्षा निर्देश', shelters: 'पास के सुरक्षित स्थान', safe: 'मैं सुरक्षित हूँ', help: 'मुझे मदद चाहिए' },
  ta: { title: 'Beacon', subtitle: 'உங்கள் உள்ளூர் பாதுகாப்பு உதவியாளர்', status: 'உள்ளூர் ஆபத்து நிலை', instructions: 'பாதுகாப்பு வழிமுறைகள்', shelters: 'அருகிலுள்ள பாதுகாப்பான இடங்கள்', safe: 'நான் பாதுகாப்பாக இருக்கிறேன்', help: 'எனக்கு உதவி தேவை' },
  fr: { title: 'Beacon', subtitle: 'Votre compagnon de sécurité local', status: 'État des risques locaux', instructions: 'Consignes de sécurité', shelters: 'Zones sûres à proximité', safe: 'Je suis en sécurité', help: "J’ai besoin d’aide" },
  de: { title: 'Beacon', subtitle: 'Ihr lokaler Sicherheitsbegleiter', status: 'Lokale Gefahrenlage', instructions: 'Sicherheitshinweise', shelters: 'Sichere Orte in der Nähe', safe: 'Ich bin in Sicherheit', help: 'Ich brauche Hilfe' },
  ja: { title: 'Beacon', subtitle: '地域の安全をサポート', status: '地域の危険状況', instructions: '安全に関する指示', shelters: '近くの安全な避難場所', safe: '安全です', help: '助けが必要です' },
}

function App() {
  const [language, setLanguage] = useState<Language>('en')
  const [checkIn, setCheckIn] = useState<'safe' | 'help' | null>(null)
  const t = translations[language]

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#" aria-label="Beacon home">
          <span className="brand-icon">B</span>
          <span>{t.title}</span>
        </a>
        <span className="mode-badge">REPLAY · DEMO</span>
      </header>

      <section className="welcome">
        <p className="eyebrow">TRAVEL SAFETY NETWORK</p>
        <h1>{t.subtitle}</h1>
        <p className="muted">Illustrative reconstruction — not live emergency information.</p>
        <label className="language-picker">
          <span>Language / மொழி / भाषा</span>
          <select value={language} onChange={(event) => setLanguage(event.target.value as Language)}>
            <option value="en">English</option>
            <option value="hi">हिन्दी</option>
            <option value="ta">தமிழ்</option>
            <option value="fr">Français · Unreviewed</option>
            <option value="de">Deutsch · Unreviewed</option>
            <option value="ja">日本語 · Unreviewed</option>
          </select>
        </label>
      </section>

      <section className="status-card" aria-labelledby="status-heading">
        <div className="card-heading">
          <span className="status-symbol">!</span>
          <div>
            <p className="eyebrow">CURRENT AREA</p>
            <h2 id="status-heading">{t.status}</h2>
          </div>
          <span className="status-label">UNVERIFIED</span>
        </div>
        <h3>Community flood report</h3>
        <p className="muted">A report has been received, but it has not been independently confirmed.</p>
        <div className="status-footer">
          <span>Evidence: community report</span>
          <span>Demo data</span>
        </div>
      </section>

      <div className="content-grid">
        <section className="panel">
          <div className="panel-title">
            <span className="panel-icon">↗</span>
            <h2>{t.instructions}</h2>
          </div>
          <ul className="instruction-list">
            <li>Avoid flooded roads and underpasses.</li>
            <li>Never walk or drive through floodwater.</li>
            <li>Follow verified official announcements.</li>
            <li>Keep your phone charged and accessible.</li>
          </ul>
          <p className="notice">These are general demo instructions. Follow local emergency services for real incidents.</p>
        </section>

        <section className="panel">
          <div className="panel-title">
            <span className="panel-icon">⌖</span>
            <h2>{t.shelters}</h2>
          </div>
          <article className="shelter">
            <div className="shelter-pin">1</div>
            <div>
              <h3>Demo Community Shelter</h3>
              <p className="muted">Illustrative location · Availability unverified</p>
              <span className="demo-tag">DEMO — NOT VERIFIED</span>
            </div>
          </article>
          <p className="notice">No live shelter data is connected yet. Verify shelter availability with local authorities.</p>
        </section>
      </div>

      <section className="checkin-panel">
        <div>
          <p className="eyebrow">YOUR STATUS</p>
          <h2>Are you safe?</h2>
          <p className="muted">Demo only — your response is not sent to emergency services.</p>
        </div>
        <div className="checkin-actions">
          <button className="safe-button" onClick={() => setCheckIn('safe')}>✓ {t.safe}</button>
          <button className="help-button" onClick={() => setCheckIn('help')}>! {t.help}</button>
        </div>
        {checkIn && (
          <p className="feedback" role="status">
            Demo selection: {checkIn === 'safe' ? t.safe : t.help}. No check-in was sent.
          </p>
        )}
      </section>

      <footer>
        <span>BEACON · STREETVERISM</span>
        <span>Illustrative demo · Not an official emergency service</span>
      </footer>
    </main>
  )
}

export default App