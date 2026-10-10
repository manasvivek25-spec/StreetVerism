# StreetVerism 2–3 Minute Demo Script & Click Path

> **Hackathon Presentation & Video Demonstration Guide**  
> Target Duration: 2 minutes 30 seconds  
> Scope: End-to-end walkthrough of the 5-step MVP Golden Path.

---

## 1. Setup & Starting State

1. **Backend**: Deployed and started in Replay mode (`MOCK=0`, `REPLAY_AUTOSTART=golden_moment`).
2. **Tourist Client**: Open on a mobile device or responsive browser window at `/`.
3. **Authority Console**: Open in a second window/tab at `/console`.

---

## 2. Step-by-Step Click Path & Script

### Act 1: The Foreign Tourist Experience (0:00 – 1:00)
**Presenter Narration:**
> *"Imagine you are a foreign tourist visiting Chennai during an extreme weather event like Cyclone Michaung. You don't speak Tamil, your hotel is flooded, and social media is flooded with conflicting rumors. You scan the emergency QR code in your hotel lobby to open StreetVerism."*

1. **Language Selection**:
   - In the Language dropdown, select **Deutsch (German)**.
   - **Observe**: The entire interface updates into German (`"Lokale Gefahrenlage"`, `"Sicherheitshinweise"`).
   - **Honesty in Translation**: Point to the instruction list. Notice the orange badge: **"⚠️ Machine-translated"**. Below it, the English original is clearly displayed (*"Move to higher ground immediately. Do not wait."*). Only English is verified as human-reviewed; other languages are marked as unreviewed machine translations.
2. **Replay Disclaimer**:
   - Show the purple banner at the top: **"REPLAY: ILLUSTRATIVE RECONSTRUCTION"** with the official disclaimer: *"Simulated data based loosely on a past event, not real or official."*
3. **H3 Spatial Map**:
   - Scroll to the Leaflet map. H3 resolution-8 hexagons are rendered:
     - **Red Hexagons**: Adyar official hazard zone.
     - **Yellow Hexagons**: Central Zone unverified rumor cluster.
     - **Green Hexagons**: Calm Zone clear weather.
   - Click on the yellow cell: notice the **"UNVERIFIED"** status with the distinct dashed yellow warning card advising tourists to disregard social rumors and await official advisories.

---

### Act 2: Safe Shelter & Emergency Navigation (1:00 – 1:35)
**Presenter Narration:**
> *"When water rises, tourists need concrete action, not vague advisories. StreetVerism computes the nearest registered shelter and provides one-tap navigation."*

1. **Nearby Shelters**:
   - Scroll to **"Sichere Orte in der Nähe" (Nearby Safe Zones)**.
   - Notice **Demo Cyclone Center - Saidapet** (702m away, 🟢 Open, Capacity: 420).
   - Point out that duplicate local names are hidden when identical to the primary name.
2. **One-Tap Maps Deep Link**:
   - Click **"🗺️ Open in Google Maps ↗"**.
   - Opens turn-by-turn directions directly in the native map application with destination coordinates pre-filled.

---

### Act 3: Rescue Check-in & Authority Dashboard Triage (1:35 – 2:10)
**Presenter Narration:**
> *"If a tourist is trapped or in distress, they shouldn't have to fill out complex forms while their phone battery is dying."*

1. **Tourist Check-in**:
   - Under **"STATUS CHECK-IN"**, tap the red button: **"🚨 Ich brauche Hilfe" (I need help)**.
   - Notice confirmation message: *"🆘 Help request submitted (ID: chk_...). Transmitted to safety console."*
   - Note rate limiting protection: button enters cooldown with Retry-After timer preventing abuse.
2. **Switch to Authority Console (`/console`)**:
   - Authenticate with the secure `AUTHORITY_KEY`.
   - On the **Check-in Triage Dashboard**, show the tourist's help request appearing within seconds.
   - The help request is sorted right at the top of the queue in high-contrast red.
   - Language breakdown shows German (`DE: 1`).
   - Group size and GPS coordinates are shown with zero PII stored (device ID is completely omitted for privacy).
   - Click **"Mark Handled"**: toggles the check-in status to handled, turning the queue row green.

---

### Act 4: Scenario Control & Live Broadcast (2:10 – 2:30)
**Presenter Narration:**
> *"The Authority Console also gives incident commanders the power to simulate past events or switch seamlessly to real-time operations."*

1. **Scenario & Demo Controls (`/console` Tab: ⏱️ Scenario & Demo)**:
   - Point to the active simulation clock at `golden_moment` (+09h30m).
   - Demonstrate seeking to another bookmark (e.g., `Early Warning` or `All-Clear Contradicted`).
   - Click **"🔄 Reset Scenario to Live Mode"**.
   - The backend switches from replay reconstruction to `LIVE DISPATCH`.
2. **Live Alert Publishing**:
   - Go to **"📝 Publish Alert"** tab.
   - Select Hazard: *Cyclone*, Zone: *Saidapet Riverbank*, Instructions: *EVACUATE_TO_SHELTER*.
   - Click **"🚀 Broadcast Official Alert"**.
   - Switch back to the tourist app: the new live alert instantly renders across all connected tourist clients.

---

## 3. Summary of Key Achievements
- **Honesty First**: Never misrepresents replay simulations or machine translations as verified official facts.
- **Robust Privacy**: Strict zero-tracking policy; device IDs never leaked to dispatch views.
- **Bayesian Rigor**: Synthesizes rainfall forecast data, crowd report clusters, and official CAP polygons into calibrated posterior log-odds.
- **Fail-Safe Operation**: Direct-line fallbacks, reverse-proxy IP rate limiting, and zero-error API design.
