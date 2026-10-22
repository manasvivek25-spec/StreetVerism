package org.streetverism.app.trust

import org.junit.Assert.*
import org.junit.Test
import org.streetverism.app.model.HazardStatus
import org.streetverism.app.model.UserProfile

class BayesianTrustEngineTest {

    @Test
    fun testUserProfileAgeCredibilityAndVulnerability() {
        val child = UserProfile("Tommy", 10, "en", "United Kingdom")
        val teen = UserProfile("Liam", 16, "en", "Australia")
        val adult = UserProfile("Elena", 32, "de", "Germany")
        val senior = UserProfile("Arthur", 74, "fr", "France")

        // Credibility Multipliers
        assertEquals(0.50f, child.calculateCredibilityFactor(), 0.001f)
        assertEquals(0.75f, teen.calculateCredibilityFactor(), 0.001f)
        assertEquals(1.00f, adult.calculateCredibilityFactor(), 0.001f)
        assertEquals(0.90f, senior.calculateCredibilityFactor(), 0.001f)

        // Vulnerability Triage flags
        assertTrue("Child must be flagged vulnerable", child.isVulnerable())
        assertFalse("Adult is not vulnerable", adult.isVulnerable())
        assertTrue("Senior must be flagged vulnerable", senior.isVulnerable())
    }

    @Test
    fun testDryBaselinePriorProbability() {
        val priorLogit = BayesianTrustEngine.computePriorLogit(0f, 0f, false)
        assertEquals(-4.0f, priorLogit, 0.001f)
        val pDry = BayesianTrustEngine.sigmoid(priorLogit)
        assertEquals(0.017986f, pDry, 0.001f)
    }

    @Test
    fun testOfficialAlertOverridesToHazard() {
        val assessment = BayesianTrustEngine.assess(
            currentTimestampSeconds = 10000L,
            hasOfficialHazardAlert = true
        )

        assertEquals(HazardStatus.OFFICIAL_HAZARD, assessment.status)
        assertEquals(0.99f, assessment.pHazard, 0.001f)
    }

    @Test
    fun testAgeCredibilityInfluencesCrowdLogit() {
        val now = 10000L
        val childReport = LocalReport(
            id = "r_child",
            deviceId = "dev_1",
            reporterAge = 11,
            claim = "flooded",
            timestampSeconds = now
        )

        val adultReport = LocalReport(
            id = "r_adult",
            deviceId = "dev_2",
            reporterAge = 35,
            claim = "flooded",
            timestampSeconds = now
        )

        // Child report alone (scaled by 0.50x)
        val assessChild = BayesianTrustEngine.assess(
            currentTimestampSeconds = now,
            reports = listOf(childReport)
        )

        // Adult report alone (scaled by 1.00x)
        val assessAdult = BayesianTrustEngine.assess(
            currentTimestampSeconds = now,
            reports = listOf(adultReport)
        )

        assertTrue(
            "Adult report should contribute greater evidence weight than uncorroborated child report",
            assessAdult.crowdLogitRaw > assessChild.crowdLogitRaw
        )
    }

    @Test
    fun testTwoHourHalfLifeDecay() {
        val t0 = 10000L
        val t2h = t0 + 7200L // 2 hours later

        val freshReport = LocalReport("r1", "d1", 30, "Alice", "flooded", t0)

        val assessImmediate = BayesianTrustEngine.assess(t0, reports = listOf(freshReport))
        val assessAfter2h = BayesianTrustEngine.assess(t2h, reports = listOf(freshReport))

        // After exactly 1 half-life (7200s), crowd logit must be roughly half
        assertEquals(
            assessImmediate.crowdLogitRaw * 0.5f,
            assessAfter2h.crowdLogitRaw,
            0.05f
        )
    }
}
