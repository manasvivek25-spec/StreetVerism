# StreetVerism Replay Engine: Architecture & Scenario Specification

> **Replay: illustrative reconstruction**: Simulated data based loosely on a past event, not real or official.

---

## 1. What It Is

The **StreetVerism Replay Engine** is a deterministic, seek-safe temporal projection engine that models crisis communication, official alert lifecycles, and crowd report verification during severe weather events.

It models an illustrative reconstruction of the **December 2023 Cyclone Michaung Chennai Floods**, spanning **24 simulated hours** from **2023-12-04T00:00:00Z** (05:30 IST) to **2023-12-05T00:00:00Z** (05:30 IST).

### Pure Functional Architecture & Seek Safety
The state of the world is modeled as a **pure function** of `(scenario, t)`:
$$\text{State}(t) = f(\text{Scenario}, t)$$

- **Stateless Projection**: Seeking backward or forward in time yields mathematically identical outputs regardless of prior seek history.
- **Dynamic Replay Overlay**: Runtime user reports submitted during replay are held in an in-memory ring buffer (up to 1,000 items) and timestamped at the current sim time. Seeking backward does not reveal future dynamic reports; seeking forward incorporates them.
- **Thread-Safe Scenario Clock**: An injectable `wall_clock` callable drives simulated time:
  $$\text{sim\_time} = \text{anchor\_sim} + (\text{wall\_now} - \text{anchor\_wall}) \times \text{speed}$$
  supporting speeds from $0.0$ (paused) to $3600.0\times$ wall clock.

---

## 2. Honesty & Ethical Calibration

To prevent misinformation, confusion, or false attribution:
1. **Generic Issuing Authority**:
   Alerts are issued strictly by `"State Disaster Authority (replay)"` with `source="replay"` and `is_replay=true`. No alerts are attributed to real government agencies.
2. **Fictional Demonstration Shelters**:
   All evacuation centers use fictional demonstration identifiers and names (e.g. `"Demo Relief Center - Velachery"`), with `is_demo=true`.
3. **Illustrative Flood Risk Boundaries**:
   `data/flood_prone.geojson` uses hand-drawn approximate polygons representing vulnerable drainage basins in Chennai, carrying an explicit `"note"` stating that it is illustrative and not an official hazard map.
4. **Approximate Parameters**:
   Top-level scenario metadata declares `"values_are_approximate": true`.

---

## 3. Five Modeled Chennai Zones

| Area Group | Zone Name | Terrain Class | Peak Rain (3h / 24h) | Narrative Role | Representative Res-8 Cell |
|---|---|---|---|---|---|
| **Group 1** | Velachery / Pallikaranai | Flood-prone marshland | 120 mm / 320 mm | Heaviest flood basin; early heavy rain alert, mid-day severe flood evacuation | `88618c4e6bfffff` |
| **Group 2** | Adyar / Saidapet | Flood-prone river corridor | 50 mm / 120 mm | **Early-warning storyline**: crowd reports corroborate flood prior to official warning | `88618c4f1dfffff` |
| **Group 3** | Central Rumor Zone | Non-flood-prone | 32 mm / 60 mm | **Viral rumor storyline**: 3 bot waves collapse to unverified, contradicted by official all-clear | `88618c4d49fffff` |
| **Group 4** | Coastal Zone | Non-flood-prone | 40 mm / 80 mm | Coastal warning zone; advisory against coastal visits | `88618c4a91fffff` |
| **Group 5** | Calm Zone (Northwest Ridge) | Non-flood-prone | 0.0 mm / 0.0 mm | **Negative baseline**: dry throughout, safe reports only, status `clear` for 24 hours | `88618c4dadfffff` |

---

## 4. Modeled Narrative Storylines

### Storyline A: Early Warning in Adyar (Group 2)
1. **06:50 UTC (12:20 IST)**: Rain ramps up. Terrain is flood-prone. Status is `clear`.
2. **07:00 UTC (12:30 IST)**: Report 1 arrives (*"Kasi bridge underpass completely submerged"*). Single cluster $\implies$ status transitions to `unverified` ($p = 0.78$).
3. **07:25 UTC (12:55 IST)**: Report 2 arrives (*"Water entering houses near Saidapet metro station"*), spaced 25 min apart from distinct hardware device ID.
4. **07:30 UTC (13:00 IST)**: Engine corroborates 2 independent clusters in flood-prone terrain. **Status upgrades to `likely_hazard` ($p = 0.93$)** and safety headline displays `AVOID_FLOODED_ROADS` — **90 minutes before any official agency broadcast**.
5. **07:50 UTC (13:20 IST)**: Report 3 arrives (*"Adyar river overflowing onto arterial road"*).
6. **09:00 UTC (14:30 IST)**: State Disaster Authority issues extreme flood alert (`alt_rep_adyar_extreme`). **Status immediately upgrades to `official_hazard` ($p = 0.99$)** with headline `MOVE_TO_HIGHER_GROUND`.

### Storyline B: Coordinated Viral Rumor in Central Zone (Group 3)
1. **08:00 UTC (13:30 IST) - Wave 1**: 40 duplicate reports posted within 10 minutes from 40 synthetic devices claiming catastrophic flooding.
   - *Engine Defense*: 3-gram text clustering merges all 40 reports into **exactly 1 cluster**. Because local rain is moderate and terrain is non-flood-prone, prior $p$ is $0.08$. The single cluster cannot bridge the gap to $0.80$. Status stays `unverified` ($p = 0.29$).
2. **09:15 UTC (14:45 IST) - Wave 2**: 20 new devices post fresh claims.
   - *Engine Defense*: A second cluster forms. Even with crowd logit clipping ceiling ($+3.0$), posterior logit $-2.30 + 3.00 = +0.70 \implies p = 0.67 < 0.80$. Status remains `unverified`.
3. **10:30 UTC (16:00 IST) - Wave 3**: 20 new devices post urgent claims.
   - *Engine Defense*: Forms a third cluster. The $+3.0$ logit ceiling prevents panic escalation. Status remains `unverified`.
4. **11:00 UTC (16:30 IST) - Official All-Clear**: Authority inspects the junction and issues an official `all_clear` notice.
   - *Engine Defense*: Because active positive claims exist, the engine marks the zone **`contradicted` ($p = 0.01$)** with headline `FOLLOW_OFFICIAL_ONLY` and summary: *"Claim contradicted by official all-clear from State Disaster Authority (replay)"*.
5. **16:30 UTC (22:00 IST) - Aging Out**: 6 hours after the earliest report of Wave 3 (10:30 UTC), all crowd clusters age out past the active threshold (`age_s > 21600`).
   - *Engine Defense*: With zero active positive claims remaining and the official all-clear still active, the cell transitions to **`clear` ($p = 0.01$)** with headline `ALL_CLEAR`.

### Storyline C: Negative Baseline in Calm Zone (Group 5)
- Located on elevated ground in Northwest Chennai.
- Precipitation is 0 mm throughout the event.
- Several tourist and citizen "safe" observations are recorded.
- Status remains `clear` ($p \le 0.02$) across all 24 simulated hours.

---

## 5. Replay Demo & Timeline Outputs

Run the deterministic timeline script from repository root:
```powershell
python backend/scripts/replay_demo.py
```

### 24-Hour Simulated Reconstruction Timeline

| Sim Hour | UTC Time | IST Time | Velachery (G1) | Adyar (G2) | Rumor Zone (G3) | Coastal (G4) | Calm Zone (G5) |
|---|---|---|---|---|---|---|---|
| +00 h | 00:00Z | 05:30 IST | `clear` (0.17) | `clear` (0.10) | `clear` (0.02) | `clear` (0.03) | `clear` (0.02) |
| +01 h | 01:00Z | 06:30 IST | `official_hazard` (0.99) | `clear` (0.13) | `clear` (0.03) | `official_hazard` (0.99) | `clear` (0.02) |
| +02 h | 02:00Z | 07:30 IST | `official_hazard` (0.99) | `clear` (0.16) | `clear` (0.03) | `official_hazard` (0.99) | `clear` (0.01) |
| +03 h | 03:00Z | 08:30 IST | `official_hazard` (0.99) | `clear` (0.20) | `clear` (0.04) | `official_hazard` (0.99) | `clear` (0.01) |
| +04 h | 04:00Z | 09:30 IST | `official_hazard` (0.99) | `clear` (0.24) | `clear` (0.05) | `official_hazard` (0.99) | `clear` (0.01) |
| +05 h | 05:00Z | 10:30 IST | `official_hazard` (0.99) | `clear` (0.30) | `clear` (0.06) | `official_hazard` (0.99) | `clear` (0.01) |
| +06 h | 06:00Z | 11:30 IST | `official_hazard` (0.99) | `clear` (0.35) | `clear` (0.07) | `official_hazard` (0.99) | `clear` (0.01) |
| +07 h | 07:00Z | 12:30 IST | `official_hazard` (0.99) | `unverified` (0.78) | `clear` (0.07) | `official_hazard` (0.99) | `clear` (0.01) |
| +08 h | 08:00Z | 13:30 IST | `official_hazard` (0.99) | `likely_hazard` (0.95) | `unverified` (0.29) | `official_hazard` (0.99) | `clear` (0.01) |
| +09 h | 09:00Z | 14:30 IST | `official_hazard` (0.99) | `official_hazard` (0.99) | `unverified` (0.22) | `official_hazard` (0.99) | `clear` (0.01) |
| +10 h | 10:00Z | 15:30 IST | `official_hazard` (0.99) | `official_hazard` (0.99) | `unverified` (0.43) | `official_hazard` (0.99) | `clear` (0.01) |
| +11 h | 11:00Z | 16:30 IST | `official_hazard` (0.99) | `official_hazard` (0.99) | `contradicted` (0.01) | `official_hazard` (0.99) | `clear` (0.01) |
| +12 h | 12:00Z | 17:30 IST | `official_hazard` (0.99) | `official_hazard` (0.99) | `contradicted` (0.01) | `official_hazard` (0.99) | `clear` (0.01) |
| +13 h | 13:00Z | 18:30 IST | `official_hazard` (0.99) | `official_hazard` (0.99) | `contradicted` (0.01) | `clear` (0.14) | `clear` (0.01) |
| +14 h | 14:00Z | 19:30 IST | `official_hazard` (0.99) | `official_hazard` (0.99) | `contradicted` (0.01) | `clear` (0.14) | `clear` (0.01) |
| +15 h | 15:00Z | 20:30 IST | `official_hazard` (0.99) | `official_hazard` (0.99) | `contradicted` (0.01) | `clear` (0.13) | `clear` (0.01) |
| +16 h | 16:00Z | 21:30 IST | `official_hazard` (0.99) | `official_hazard` (0.99) | `contradicted` (0.01) | `clear` (0.12) | `clear` (0.01) |
| +17 h | 17:00Z | 22:30 IST | `official_hazard` (0.99) | `official_hazard` (0.99) | `clear` (0.01) | `clear` (0.11) | `clear` (0.01) |
| +18 h | 18:00Z | 23:30 IST | `official_hazard` (0.99) | `official_hazard` (0.99) | `clear` (0.01) | `clear` (0.10) | `clear` (0.02) |
| +19 h | 19:00Z | 00:30 IST | `official_hazard` (0.99) | `official_hazard` (0.99) | `clear` (0.01) | `clear` (0.10) | `clear` (0.02) |
| +20 h | 20:00Z | 01:30 IST | `official_hazard` (0.99) | `official_hazard` (0.99) | `clear` (0.07) | `clear` (0.09) | `clear` (0.02) |
| +21 h | 21:00Z | 02:30 IST | `official_hazard` (0.99) | `official_hazard` (0.99) | `clear` (0.07) | `clear` (0.09) | `clear` (0.02) |
| +22 h | 22:00Z | 03:30 IST | `official_hazard` (0.99) | `official_hazard` (0.99) | `clear` (0.06) | `clear` (0.08) | `clear` (0.02) |
| +23 h | 23:00Z | 04:30 IST | `official_hazard` (0.99) | `official_hazard` (0.99) | `clear` (0.05) | `clear` (0.07) | `clear` (0.02) |
| +24 h | 00:00Z | 05:30 IST | `unverified` (0.87) | `clear` (0.38) | `clear` (0.05) | `clear` (0.07) | `clear` (0.02) |

### Key Storyline Bookmarks

| Bookmark | Offset | IST Time | Adyar (G2) | Rumor Zone (G3) | Calm Zone (G5) | Narrative Description |
|---|---|---|---|---|---|---|
| `early_warning` | +07h30m | 13:00 IST | `likely_hazard` (0.93) | `clear` (0.08) | `clear` (0.01) | Crowd reports corroborate flood hazard in Adyar before official alert |
| `viral_rumor` | +08h30m | 14:00 IST | `likely_hazard` (0.96) | `unverified` (0.25) | `clear` (0.01) | Coordinated rumor wave 1 in Central Zone collapses to unverified |
| `golden_moment` | +09h30m | 15:00 IST | `official_hazard` (0.99) | `unverified` (0.51) | `clear` (0.01) | Adyar upgraded to official_hazard, Central Zone unverified, Calm Zone clear |
| `all_clear_contradicted` | +11h30m | 17:00 IST | `official_hazard` (0.99) | `contradicted` (0.01) | `clear` (0.01) | Official all-clear contradicts rumors in Central Zone |
| `claims_aged_out` | +17h00m | 22:30 IST | `official_hazard` (0.99) | `clear` (0.01) | `clear` (0.01) | Rumor reports age out beyond 6 hours, Central Zone returns to clear |

---

## 6. Practical Guidance: Running the Demo & Video Recordings

- **Recommended Playback Speeds**:
  - For **live user walkthroughs**: Use speed `1x` to `60x`.
  - At speed `60x`, 1 minute of real time covers 1 hour of simulated crisis response.
- **Why Not Speed 600x for Recordings?**:
  - A crowd report has a 2-hour half-life ($7,200\text{ seconds}$). At speed `600x`, those 2 hours evaporate in only **12 wall-clock seconds**!
  - For screen recordings and video presentations, **use discrete seek** (or bookmark jumps) rather than ultra-high multiplier playback, giving judges sufficient time to observe the transitions and evidence breakdowns.

---

## 7. Tuning Calibration & Verification

### Rumor Zone Rain Calibration Target
- Required: Prior $p_0 \in [0.06, 0.12]$ across the entire rumor window ($08:00$ to $16:30$ sim time).
- With hand-set weights ($\beta_0 = -4.0, \beta_{3h} = 0.04, \beta_{24h} = 0.01$ on non-flood-prone terrain):
  $$\text{prior\_logit} = -4.0 + 0.04 \cdot r_{3h} + 0.01 \cdot r_{24h}$$
- At $r_{3h} = 28\text{ mm}, r_{24h} = 45\text{ mm}$: $\text{prior\_logit} = -2.43 \implies p_0 = 0.0809$.
- At $r_{3h} = 32\text{ mm}, r_{24h} = 55\text{ mm}$: $\text{prior\_logit} = -2.17 \implies p_0 = 0.1025$.
- Over all 510 minutes of the rumor window:
  - Minimum prior $p$: **0.0809**
  - Maximum prior $p$: **0.1025**
  - Maximum possible posterior with full $+3.0$ crowd ceiling clip: **0.6964 < 0.80**.
- **Result**: Even if bots post thousands of rumors across distinct devices, the crowd ceiling prevents reaching `likely_hazard` because weather conditions do not warrant it.

---

## 8. Limitations & Boundary Assumptions

1. **Synthetic Timelines**: The timeline is an illustrative reconstruction modeled from qualitative news and agency post-incident reports, not high-resolution millimeter gauge telemetry.
2. **Static GeoJSON Polygons**: Weather keyframes are linearly interpolated across static 2D planar polygons rather than continuous numerical weather prediction (NWP) radar velocity fields.
3. **Discrete H3 Centroid Evaluation**: Cells are mapped to area groups and flood-prone basins via their geographic centroids (`cell_to_latlng`). Boundary edge cells bisected by group borders adopt the group containing their center.
