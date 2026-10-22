# StreetVerism Offline-First Android Application (Kotlin)

The StreetVerism Android application is a mission-critical, native Kotlin application built for extreme hydrological disasters and power grid failures. It provides 100% offline survivability, an uncluttered calming crisis map, an age-based credibility verification engine, a complete pre-packaged crisis translator, basic survival amenities discovery, weather precautions, and emergency first-aid protocols.

---

## 1. Architectural Highlights & Zero-Network Guarantees

```
+-----------------------------------------------------------------------------------+
|                        STREETVERISM ANDROID ARCHITECTURE                          |
+-----------------------------------------------------------------------------------+
|  [ User Profile ]         [ On-Device Trust Engine ]    [ P2P Crisis Mesh ]       |
|  - Name, Age, Lang, Nat   - Kotlin Bayesian Fusion      - BLE / Wi-Fi Ad-hoc      |
|  - Age Credibility Multi  - Prior (-4.0) + Topography   - Store & Forward Relays  |
|  - Vulnerability Triage   - 2h Temporal Decay           - Zero-Cell Tower Comms   |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [ Intuitive Crisis Map ]      [ Offline Amenities ]     [ Complete Translator ]  |
|  - Vector 2D Canvas (No Tiles) - Hospitals (24x7)        - 7 Emergency Categories |
|  - Azimuth Escape Compass      - Water & Food Points     - Native + Phonetic Text |
|  - Low Cognitive Load UI       - Pharmacies & First Aid  - Fullscreen Flashcards  |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [ Weather Precautions & Safety ]          [ Step-by-Step Triage First Aid ]      |
|  - Flooding, Cyclone, Live Power Lines     - Hands-Only CPR & Drowning Recovery   |
|  - Sanitation & Disease Prevention         - Severe Bleeding & Tourniquet Guide   |
|  - "DO" vs "DO NOT" Critical Checklists    - Fractures, Hypothermia, Burns        |
+-----------------------------------------------------------------------------------+
|                 Bundled On-Device JSON Assets (Zero Cloud Dependency)             |
+-----------------------------------------------------------------------------------+
```

---

## 2. Minimal 4-Field Profile & Age Credibility Engine

### The Problem
During disasters, lengthy forms cause panic and abandoned onboarding. Conversely, anonymous social claims can spread viral hoaxes (e.g. false dam breaches).

### The Solution (`org.streetverism.app.model.UserProfile`)
The app prompts for **strictly 4 essential fields**:
1. **Full Name**
2. **Age**
3. **Preferred Crisis Language** (English, Tamil, Hindi, German, French, Japanese, Spanish)
4. **Nationality** (for consular aid and embassy contact)

### Age-Credibility & Humanitarian Priority Multiplier
The on-device Bayesian engine calibrates crowd observation weights based on the reporter's age demographic:

| Age Range | Demography | Credibility Multiplier | Humanitarian Rescue Priority |
|---|---|---|---|
| `< 14` | Child | **0.50x** | 🚨 **High Rescue Priority** (Automated child vulnerability flag) |
| `14 - 17` | Youth | **0.75x** | Standard |
| `18 - 64` | Adult | **1.00x** | Standard civilian observer |
| `65+` | Senior Citizen | **0.90x** | 🩺 **Priority Medical Triage** (Urgent medical/mobility vulnerability) |

*Formula*:
$$\text{Effective LLR}(E_i) = \text{Base LLR}(E_i) \times \text{Credibility Multiplier}(\text{Age}) \times \exp(-\lambda \Delta t)$$

---

## 3. Calming, Intuitive Crisis Map UI

### Low-Cognitive-Load Design Principles
In extreme panic (surging water, dark storm), standard civilian street maps with hundreds of labels cause sensory overload and disorientation.

The StreetVerism map view (`IntuitiveCrisisMap.kt`) provides:
1. **Escape Compass Needle**: A large, bold azimuth arrow at the top of the screen pointing directly to the nearest open relief centre (e.g. `🧭 ↖ Head NW · 450m (6 min walk) to Saidapet Relief Centre`). Users do not even need to read the map to escape danger.
2. **Vector Polygons without Tile Servers**: Shaded hazard zones (Red: Official Hazard, Orange: Likely Hazard, Amber: Unverified Rumors, Green: Clear Refuge) rendered dynamically using Android Canvas.
3. **Interactive Resource Markers**:
   - 🛡️ Safe Shelters (Purple)
   - 🏥 Hospitals & Trauma Centers (Red)
   - 💊 Pharmacies & Emergency Medicines (Green)
   - 🍲 Food Distribution & Clean Water (Blue)
   - 🩹 First Aid Outposts (Amber)
4. **1-Tap Amenity Inspector**: Shows distance in meters, walking duration, 24x7 status, emergency telephone number, and supplies in stock.

---

## 4. Complete Package Offline Crisis Translator

The translator (`TranslatorScreen.kt`) is **fixed-coded and pre-packaged**, eliminating external cloud translation APIs:
- **7 Core Emergency Categories**:
  1. `🚨 Life SOS & Rescue` (Trapped, water rising, drowning, elderly/baby with us)
  2. `🏥 Medical & First Aid` (Heavy bleeding, chest pain, broken bone, need insulin/inhaler)
  3. `🍲 Clean Water & Food` (Clean water point, is water safe to drink, emergency rations)
  4. `🧭 Evacuation & Roads` (Safe road to high ground, road submerged/flooded, nearest shelter)
  5. `🛡️ Police & Civil Defence` (Civil defence officers, fallen live power lines danger)
  6. `🛂 Tourist & Embassy Help` (Foreign tourist identification, contact consulate/family)
  7. `⚡ Shelter & Essentials` (Dry blankets, 10-minute phone emergency charging, dry clothes)
- **Supported Languages**: English, தமிழ் (Tamil), हिन्दी (Hindi), Deutsch (German), Français (French), 日本語 (Japanese), Español (Spanish).
- **Phonetic Transliteration**: Non-Tamil or non-Hindi tourists can speak the phrase aloud using English phonetics (e.g. *"Udhavi! Naangal ingu sikkiyullom!"*).
- **Emergency Flashcard Mode**: Tapping any phrase displays a full-screen, high-contrast modal with massive font size so a foreign tourist can simply hold up their illuminated screen to a local boatman or doctor in the dark.

---

## 5. Basic Survival Amenities Registry

Stored in `assets/amenities.json`:
- **Emergency Hospitals**: Multi-specialty trauma centers with emergency surgical capacity, intensive care, and oxygen beds.
- **24x7 Pharmacies**: Stocked with insulin, water purification tablets, sterile gauze, antiseptics, and inhalers.
- **Relief Food & Drinking Water Points**: Community kitchens, water tanker refill stations, and baby food distribution depots.
- **First Aid Outposts**: Paramedic-staffed dressing stations and triage posts.
- **Shelters**: High-ground facilities with power backup and sleeping cots.

Each amenity computes live offline Haversine distance, estimated walking time, and compass azimuth bearing from the user's coordinates.

---

## 6. Weather Precautions & Step-by-Step First Aid

Stored in `assets/crisis_safety_guides.json`:

### Contextual Precautions
- **Extreme Flooding**: Rules on moving water (never enter moving water > 6 inches), electrical breaker shutoff, walking stick probing for open manholes.
- **Gale Cyclones**: Window safety, interior room refuge, staying indoors during the deceptive calm "eye" of the storm.
- **Downed Electrical Lines**: 10-meter (33ft) safe radius, shuffle/hop technique for ground voltage escape, vehicle isolation rules.
- **Water Sanitation**: 3-minute boiling protocols, chlorine tablet ratios, and leptospirosis prevention.

### Step-by-Step Life Support & First Aid
- **Near-Drowning / Hands-Only CPR**: Immediate responsiveness check, 100-120 bpm continuous chest compressions (5-6 cm depth), hypothermia warming.
- **Severe Arterial Bleeding**: 10-minute uninterrupted direct pressure, elevation, and improvised tourniquet guidelines.
- **Bone Fractures & Splints**: Non-reduction rule, rigid splint immobilization, circulation checks.
- **Hypothermia & Cold Shock**: Dry environment, core warming, avoiding rough movement.
- **Electrical Burns**: Non-conductive disconnection, burn cooling with clean water, sterile wrapping.
- **Floodwater Snakebite**: Venom containment, immobilization below heart level, anti-venom hospital transport.

---

## 7. Zero-Network P2P Crisis Mesh

The app integrates `LocalMeshManager.kt`, which formats distress check-ins and hazard observations into compact `MeshPacket` payloads:
- Communicates peer-to-peer over **Bluetooth Low Energy (BLE)** advertising and Wi-Fi Ad-hoc / Direct.
- Operates on a **Store-and-Forward** model: packets jump from smartphone to smartphone across the flooded city.
- When any node in the swarm reaches an elevated relief hub or cellular tower, all queued packets automatically sync upstream to the Authority Console.

---

## 8. How to Open & Build the Project

### In Android Studio
1. Launch **Android Studio**.
2. Select **Open** and choose the `android/` directory inside this repository (`c:\Users\len\StreetVerism\android`).
3. Android Studio will automatically recognize the Kotlin DSL configuration (`build.gradle.kts`, `libs.versions.toml`).
4. Click **Run** (`Shift + F10`) or select an Emulator / connected Android device running Android 8.0+ (API 26 to 35).

### Command Line Build
Using the Gradle wrapper:
```powershell
cd android
.\gradlew.bat assembleDebug
```
The compiled debug APK will be generated at:
`android/app/build/outputs/apk/debug/app-debug.apk`
