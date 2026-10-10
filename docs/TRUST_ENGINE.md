# StreetVerism Bayesian Trust Engine

The StreetVerism Trust Engine is a pure functional, explainable crisis evaluation engine designed for foreign tourists and local authorities during extreme meteorological events. It fuses official Common Alerting Protocol (CAP) feeds, radar/satellite rainfall observations, topographical vulnerability indices, and crowdsourced incident reports into calibrated, actionable risk assessments.

---

## 1. Executive Summary & Plain Language Overview

During catastrophic weather emergencies (such as Cyclone Michaung or the 2015 Chennai floods), tourists face two compounding hazards:
1. **Official alert delays & spatial coarseness**: Authoritative alerts often take hours to formalize and cover broad administrative districts rather than specific flooded underpasses.
2. **Social media rumor inflation & panic**: Unverified panic posts, forwarded WhatsApp videos, and coordinated rumors cause gridlock or misdirected evacuations.

The StreetVerism Trust Engine solves this via a **principled Bayesian evidence fusion architecture**:
- **Baseline weather model**: Rainfall accumulation and topography set an evidence-based prior probability of hazard for each local H3 resolution-8 cell (~450 meters diameter).
- **Crowd clustering with conservative deduplication**: Incoming crowd reports are clustered via Union-Find and character 3-gram text similarity so that 50 copies of the same rumor or single-device spam count as only **one** report.
- **Exponential temporal decay**: Fresh reports carry maximum weight, decaying with an exact 2-hour half-life so outdated road conditions automatically fade out.
- **Mathematical bounding**: Total crowd influence is strictly clamped to $[-3.0, +3.0]$ log-odds, preventing Sybil attacks or mob hysteria from overtaking reality.
- **Authoritative override**: Legitimate official alerts immediately override crowd inputs, while official all-clear notices actively contradict remaining rumors.

---

## 2. Mathematical Derivation

### Conditional Independence & Log-Odds Additivity
Let $H \in \{1, 0\}$ represent the ground truth hazard state (e.g. acute road flooding or life-threatening inundation) within an H3 cell. Let $E = \{E_1, E_2, \dots, E_n\}$ denote $n$ independent pieces of evidence.

Under Bayes' Theorem:
$$P(H \mid E) = \frac{P(E \mid H) \cdot P(H)}{P(E)}$$

Expressed in odds form:
$$\text{odds}(H \mid E) = \frac{P(H \mid E)}{1 - P(H \mid E)} = \frac{P(H)}{1 - P(H)} \times \prod_{i=1}^n \frac{P(E_i \mid H)}{P(E_i \mid \neg H)}$$

Taking natural logarithms maps multiplicative odds updates into strictly linear, additive updates:
$$\ln(\text{odds}(H \mid E)) = \ln(\text{odds}(H)) + \sum_{i=1}^n \ln\left(\frac{P(E_i \mid H)}{P(E_i \mid \neg H)}\right)$$

$$\text{logit}(P(H \mid E)) = \text{logit}(P(H)) + \sum_{i=1}^n \text{LLR}(E_i)$$
where:
- $\text{logit}(p) = \ln\left(\frac{p}{1 - p}\right)$
- $\text{LLR}(E_i) = \ln\left(\frac{P(E_i \mid H)}{P(E_i \mid \neg H)}\right)$ is the Log-Likelihood Ratio of evidence $E_i$.
- Posterior probability is recovered via the standard logistic sigmoid:
  $$P(H \mid E) = \sigma(\text{posterior logit}) = \frac{1}{1 + e^{-\text{posterior logit}}}$$

---

## 3. Parameter Specification (Hand-Set)

> [!IMPORTANT]
> All coefficients and base odds below are **HAND-SET** and tuned against historical rainfall replay benchmarks (Cyclone Michaung, December 2023). They are not fitted via regression on massive historical labels.

### Prior Parameters
$$\text{logit}(p_0) = \beta_0 + \beta_{3h} \cdot r_{3h} + \beta_{24h} \cdot r_{24h} + \beta_{\text{flood}} \cdot f_{\text{flood}}$$

| Parameter | Value | Description |
|---|---|---|
| $\beta_0$ | **-4.0** | Baseline dry-weather logit odds ($p_0 \approx 0.018$ or $1.8\%$) |
| $\beta_{3h}$ | **+0.04** / mm | Weight per millimeter of 3-hour rainfall accumulation |
| $\beta_{24h}$ | **+0.01** / mm | Weight per millimeter of 24-hour antecedent rainfall |
| $\beta_{\text{flood}}$ | **+1.50** | Terrain penalty for low-elevation / flood-prone drainage basins |
| $\text{MAX\_RAIN\_3H}$ | **150.0 mm** | Hard saturation cap on 3-hour rainfall |
| $\text{MAX\_RAIN\_24H}$ | **400.0 mm** | Hard saturation cap on 24-hour rainfall |

### Reporter Reliability & LLR Calibration
For an observer reporting with sensitivity $s = P(\text{Positive} \mid H)$ and specificity $q = P(\text{Negative} \mid \neg H)$:
- Positive hazard claim (`flooded`, `blocked`): $\text{LLR}_+ = \ln\left(\frac{s}{1 - q}\right)$
- Safe observation claim (`safe`): $\text{LLR}_- = \ln\left(\frac{1 - s}{q}\right)$ (strictly negative)

| Reporter Tier | Sensitivity $s$ | Specificity $q$ | Claim Type | Likelihood Ratio | Exact Theoretical LLR | Rounded Check |
|---|---|---|---|---|---|---|
| **default** | 0.70 | 0.85 | `flooded`/`blocked` | $0.70 / 0.15 = 4.6667$ | **+1.540445** | `+1.5404` |
| **default** | 0.70 | 0.85 | `safe` | $0.30 / 0.85 = 0.3529$ | **-1.041454** | `-1.0415` |
| **verified_local** | 0.90 | 0.95 | `flooded`/`blocked` | $0.90 / 0.05 = 18.000$ | **+2.890372** | `+2.8904` |
| **verified_local** | 0.90 | 0.95 | `safe` | $0.10 / 0.95 = 0.1053$ | **-2.251292** | `-2.2513` |

### Temporal Decay & Bounding
- **Half-Life ($T_{1/2}$)**: $7,200 \text{ seconds}$ (2 hours)
- **Decay Constant ($\lambda$)**: $\frac{\ln 2}{7200} \approx 9.62939 \times 10^{-5} \text{ s}^{-1}$
- **Decay Factor**: $d(t) = \exp(-\lambda \cdot \Delta t)$ where $\Delta t$ is elapsed seconds since the cluster's **earliest** report.
- **Cluster Age Thresholds**:
  - **Active Cluster**: cluster age $\Delta t \le 21,600 \text{ s}$ (6 hours). Derived decay factor: $d(21600) = 0.125$.
  - **Corroborated Cluster**: cluster age $\Delta t \le 14,400 \text{ s}$ (4 hours). Derived decay factor: $d(14400) = 0.25$.
  - *Implementation Note*: The engine evaluates cluster validity using exact elapsed seconds (`age_s <= 21600` and `age_s <= 14400`), keeping decay factor thresholds as derived analytical references to avoid floating-point epsilon discrepancies.
- **Crowd Clamping**: $\text{crowd\_logit\_clipped} = \text{clamp}(\sum \text{LLR}_i \cdot d_i(t), -3.0, +3.0)$.
- **Rain Independence**: Rain evidence enters **exclusively** via the prior; the rain line in the evidence breakdown is display-only and is never added to the posterior.

---

## 4. Five Status Classifications & Thresholds

```
                      +-----------------------------+
                      |   Official Alert Decision?  |
                      +--------------+--------------+
                                     |
                    +----------------+----------------+
                    | Yes                             | No
                    v                                 v
        +-----------------------+         +-----------------------+
        | Overlap Fraction >=0.5|         |  Likely Hazard?       |
        | Hazard: official_hazard         |  p >= 0.80 AND        |
        | All Clear: clear /             |  corroborated >= 2?   |
        |            contradicted       +-----------+-----------+
        +-----------------------+                     |
                                            +---------+---------+
                                            | Yes               | No
                                            v                   v
                                    likely_hazard    +---------------------+
                                                     | Contradicted?       |
                                                     | Active claims exist |
                                                     | AND rain_available  |
                                                     | AND prior < 0.05    |
                                                     | AND corrobrated < 2?|
                                                     +----------+----------+
                                                                |
                                                      +---------+---------+
                                                      | Yes               | No
                                                      v                   v
                                                 contradicted   +-------------------+
                                                                | Unverified?       |
                                                                | Active claims     |
                                                                | OR p >= 0.50?     |
                                                                +---------+---------+
                                                                          |
                                                                +---------+---------+
                                                                | Yes               | No
                                                                v                   v
                                                            unverified            clear
```

1. **`official_hazard`** ($p = 0.99$):
   - Overriding official alert (or union of hazard alerts) covers $\ge 50\%$ of cell area.
   - Headline: First instruction key of deciding alert (e.g. `MOVE_TO_HIGHER_GROUND`).
2. **`likely_hazard`**:
   - $p_{\text{posterior}} \ge 0.80$ AND corroborated positive clusters $\ge 2$ (clusters aged $\le 4 \text{ h}$).
   - Headline: `AVOID_FLOODED_ROADS`.
3. **`contradicted`**:
   - Active positive claims exist AND:
     - (a) Official `all_clear` alert covers $\ge 50\%$ of cell area ($p = 0.01$), OR
     - (b) `rain_available == True` AND prior $p_0 < 0.05$ AND corroborated positive clusters $< 2$.
   - Headline: `FOLLOW_OFFICIAL_ONLY`.
   - *Design Rationale*: Rule (b) strictly requires fresh rain data (`rain_available == True`). If radar or gauge feeds are missing, lack of data cannot prove the absence of a localized flood; the cell defaults to `unverified`.
4. **`unverified`**:
   - Active positive claims exist without meeting `likely_hazard` or `contradicted` criteria; OR
   - No reports exist, but weather model alone gives $p_{\text{posterior}} \ge 0.50$.
   - Headline: `UNVERIFIED_WARNING`.
5. **`clear`**:
   - $p_{\text{posterior}} < 0.50$ and no active positive claims.
   - Headline: `ALL_CLEAR` (if official all-clear covers cell) or `FOLLOW_OFFICIAL_ONLY`.

---

## 5. Architectural Guarantees

### Guarantee 1: Crowd Alone Can Never Become Official
- An `official_hazard` status is **only** reachable via verified digital signatures from authorized government disaster management authorities (parsed through CAP XML) or authenticated console publication.
- Even if hundreds of distinct devices post unverified panic reports in a cell, the maximum crowd contribution is capped at $+3.0$ log-odds. The status can reach `likely_hazard` at most, but never `official_hazard`.

### Guarantee 2: Crowd Needs Plausible Weather to Reach Likely
- On a completely dry, non-flood-prone cell ($\text{prior logit} = -4.0$):
  $$\text{posterior logit} \le -4.0 + 3.0 = -1.0 \implies p_{\text{hazard}} \le 0.2689$$
- Because $0.2689 < 0.80$, **crowd reports alone can never reach `likely_hazard` on dry ground**.
- To reach `likely_hazard`, there must be plausible antecedent/recent rainfall (or flood-prone terrain) that elevates the baseline prior, combined with at least two fresh, corroborated positive clusters.

### Guarantee 3: Chaining and Union-Find Deduplication
- Clustering groups reports using Union-Find on same-polarity reports within a 15-minute sliding window if `device_id` matches OR character 3-gram Jaccard similarity $\ge 0.60$.
- Because equivalence relations are transitive ($A \sim B \land B \sim C \implies A \sim C$), repeated reposts of the same phrasing automatically collapse into a single cluster.
- The cluster's timestamp is pinned to its **earliest** constituent report, ensuring that a coordinated bot ring reposting rumors cannot artificially keep rumors fresh.

---

## 6. Worked Examples

The following table is produced deterministically by `backend/scripts/trust_demo.py`:

| Scenario | Rain 3h | Rain 24h | Terrain | Reports | Raw Crowd | Clipped | Prior p | Final p | Status | Headline Key |
|---|---|---|---|---|---|---|---|---|---|---|
| Single fresh rumor on dry cell | 0.0 mm | 0.0 mm | Normal | 1 | +1.54 | +1.54 | 0.018 | 0.079 | `contradicted` | `FOLLOW_OFFICIAL_ONLY` |
| Single rumor on flood-prone cell | 0.0 mm | 0.0 mm | Flood-prone | 1 | +1.54 | +1.54 | 0.076 | 0.277 | `unverified` | `UNVERIFIED_WARNING` |
| 3 distinct reports with 25 mm rain (flood-prone) | 25.0 mm | 30.0 mm | Flood-prone | 3 | +4.62 | +3.00 | 0.231 | 0.858 | `likely_hazard` | `AVOID_FLOODED_ROADS` |
| 50 duplicate reports (same text) | 0.0 mm | 0.0 mm | Flood-prone | 50 | +1.54 | +1.54 | 0.076 | 0.277 | `unverified` | `UNVERIFIED_WARNING` |
| 100 distinct devices (crowd clip bound) | 0.0 mm | 0.0 mm | Normal | 100 | +154.04 | +3.00 | 0.018 | 0.269 | `unverified` | `UNVERIFIED_WARNING` |
| Decay check at t = +0 h (half-life 2 h) | 25.0 mm | 30.0 mm | Flood-prone | 1 | +1.54 | +1.54 | 0.231 | 0.584 | `unverified` | `UNVERIFIED_WARNING` |
| Decay check at t = +2 h (half-life 2 h) | 25.0 mm | 30.0 mm | Flood-prone | 1 | +0.77 | +0.77 | 0.231 | 0.394 | `unverified` | `UNVERIFIED_WARNING` |
| Decay check at t = +4 h (half-life 2 h) | 25.0 mm | 30.0 mm | Flood-prone | 1 | +0.39 | +0.39 | 0.231 | 0.307 | `unverified` | `UNVERIFIED_WARNING` |
| Decay check at t = +6 h (half-life 2 h) | 25.0 mm | 30.0 mm | Flood-prone | 1 | +0.19 | +0.19 | 0.231 | 0.268 | `unverified` | `UNVERIFIED_WARNING` |
| Official all_clear contradicting rumor | 25.0 mm | 30.0 mm | Flood-prone | 1 | +1.54 | +1.54 | 0.231 | 0.010 | `contradicted` | `FOLLOW_OFFICIAL_ONLY` |

---

## 7. Calibration Note on Borderlines & Decay

Reaching `likely_hazard` requires both plausible weather and **fresh, independent corroborating reports** (or an authenticated `verified_local` reporter):
- With 25 mm/3h of rain on flood-prone terrain ($\text{prior logit} = -1.50$), two default-tier reports that are 15 minutes old decay by $\exp(-\lambda \cdot 900) \approx 0.917$.
- Total crowd logit is $2 \times 1.5404 \times 0.917 = 2.8252$.
- Posterior logit is $-1.50 + 2.8252 = 1.3252 \implies p = \sigma(1.3252) = 0.7900$.
- Because $0.7900 < 0.80$, this borderline scenario is classified as `unverified`. This demonstrates that **staleness actively matters**: reports must either be fresher, more numerous, supported by heavier rain, or authored by a verified local tier to tip into `likely_hazard`.

---

## 8. Limitations & Edge Cases

1. **Sybil & Coordinated Manipulation**:
   - The engine bounds Sybil attacks via the $+3.0$ logit ceiling, rate-limiting per device, and 3-gram text clustering. However, a sophisticated attacker employing distinct hardware IDs and diverse LLM-generated phrasing can still reach the $+3.0$ crowd ceiling. On flood-prone cells with active rain, this can trigger `likely_hazard`.
2. **Hand-Set Weights**:
   - The weights are calibrated for Chennai coastal terrain and monsoon rainfall intensities. In arid or mountainous topographies, runoff coefficients and soil saturation curves differ significantly and would require regional recalibration.
3. **No Sensor Feedback**:
   - Ground IoT water level sensors (e.g. ultrasonic depth gauges) are not yet integrated into the prior; only gridded precipitation and static elevation vulnerability are currently modeled.
4. **Upstream Releases & Non-Rain Floods**:
   - Floods can occur without local rain (such as sudden reservoir or dam sluice gate releases, upstream river overflow, or municipal drainage/pump failures). Therefore, classifying a report as `contradicted` via low prior is strictly a **weather-plausibility judgment**, not a finding of falsehood, fake news, or debunking. The user-facing evidence explicitly states: *"No heavy rain recorded here, so this report is unconfirmed. Follow official guidance."*
