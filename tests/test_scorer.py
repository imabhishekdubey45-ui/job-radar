"""Unit tests for job_radar.scorer."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scorer import deduplicate_and_score, evaluate_job, load_config  # noqa: E402


class ScorerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(ROOT / "profile_config.json")

    def test_acme_network_sales_engineer_rejected(self) -> None:
        acme = {
            "source": "linkedin",
            "title": "Sales Engineer",
            "company": "Acme Corporation",
            "location": "123 Main Street, City, State 12345",
            "description": (
                "Architect leaf-spine architectures (VxLAN, EVPN), BGP, eBGP, OSPF, "
                "TS/SCI security clearance required, legal right to work in Japan."
            ),
            "url": "https://example.com/acme",
        }
        ev = evaluate_job(acme, self.config)
        self.assertIsNotNone(ev.rejected_reason)
        self.assertLess(ev.fit_score, 20.0)

    def test_heavy_sql_python_coding_flagged_high_risk(self) -> None:
        coding_jd = {
            "source": "naukri",
            "title": "Technical Business Analyst",
            "company": "FinData Corp",
            "location": "Bengaluru",
            "experience_text": "3-5 Yrs",
            "salary_text": "12-16 LPA",
            "description": (
                "Must write complex SQL window functions daily, pass a Python developer "
                "coding interview with DSA, and author formal BABOK BRD and UML diagrams."
            ),
            "url": "https://example.com/tech-ba",
        }
        ev = evaluate_job(coding_jd, self.config)
        self.assertEqual(ev.interview_risk, "HIGH")
        self.assertGreaterEqual(len(ev.risk_triggers), 3)

    def test_authentic_ai_ops_remote_role_scores_high_track_a(self) -> None:
        ai_ops = {
            "source": "wellfound",
            "title": "AI Operations & Workflow Automation Specialist",
            "company": "Velocity SaaS",
            "location": "Remote (India / Global)",
            "work_mode": "Remote",
            "experience_text": "3-5 years",
            "salary_text": "$30,000 - $40,000 / year",
            "skills_listed": ["AI Workflow", "Claude", "Automation", "Operations", "No-Code", "Monday.com"],
            "description": (
                "Partner with leadership to eliminate manual bottlenecks, build AI-assisted workflows "
                "using Claude, Zapier, and Monday.com, manage SLAs, SOPs, and e-commerce client onboarding."
            ),
            "url": "https://example.com/ai-ops",
        }
        ev = evaluate_job(ai_ops, self.config)
        self.assertIsNone(ev.rejected_reason)
        self.assertEqual(ev.interview_risk, "LOW")
        self.assertGreaterEqual(ev.fit_score, 75.0)
        self.assertIn("Track A", ev.recommended_resume)
        self.assertTrue(ev.salary_ok)
        self.assertTrue(ev.notice_compatible)

    def test_below_floor_salary_and_immediate_joiner_flagged(self) -> None:
        low_pay = {
            "source": "naukri",
            "title": "Operations Executive",
            "company": "SmallOps Pvt Ltd",
            "location": "Ahmedabad",
            "experience_text": "2-5 Yrs",
            "salary_text": "5-7 LPA",
            "description": "Immediate joiner only (within 15 days). Operations, SLA, vendor coordination.",
            "url": "https://example.com/low-pay",
        }
        ev = evaluate_job(low_pay, self.config)
        self.assertFalse(ev.salary_ok)
        self.assertFalse(ev.notice_compatible)
        self.assertIsNotNone(ev.notice_warning)

    def test_deduplicate_prefers_higher_score(self) -> None:
        a = {
            "source": "glassdoor",
            "title": "Operations Lead",
            "company": "Talentstream",
            "location": "Remote",
            "description": "Operations improvement",
            "url": "https://glassdoor.example/1",
        }
        b = {
            "source": "naukri",
            "title": "Operations Lead",
            "company": "Talentstream",
            "location": "Remote (Bengaluru)",
            "experience_text": "2-6 Yrs",
            "salary_text": "10-18 Lacs PA",
            "skills_listed": ["Operations", "Business process improvement", "SLA", "Automation"],
            "description": "Lead operations excellence, process improvement, SLA governance, and automation.",
            "url": "https://naukri.example/1",
        }
        results = deduplicate_and_score([a, b], self.config)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source, "naukri")

    def test_education_gate_warning_triggered(self) -> None:
        jaro = {
            "source": "Naukri.com",
            "title": "Manager Business Excellence",
            "company": "Jaro Education",
            "location": "Mumbai",
            "description": "Strictly requires dual qualification (B.E./B.Tech + full-time MBA).",
            "url": "https://example.com/jaro",
        }
        ev = evaluate_job(jaro, self.config)
        self.assertIsNotNone(ev.education_warning)
        self.assertEqual(ev.source, "naukri")

    def test_mumbai_and_gmv_and_continuous_no_false_positives(self) -> None:
        nivoda = {
            "source": "Wellfound",
            "title": "Operations Manager",
            "company": "Nivoda",
            "location": "Mumbai, India",
            "description": "B2B marketplace ($300M+ annual transactions) continuous improvement and operations automation.",
            "url": "https://example.com/nivoda",
        }
        ev = evaluate_job(nivoda, self.config)
        self.assertIsNone(ev.education_warning)
        self.assertIsNone(ev.salary_text)
        self.assertEqual(ev.location_bucket, "India-Onsite/Hybrid")

        caresource = {
            "source": "Naukri.com",
            "title": "Operations Business Analyst",
            "company": "Caresource",
            "location": "Remote",
            "work_mode": "Remote",
            "description": "Continuous process improvement in a remote environment.",
            "url": "https://example.com/caresource",
        }
        ev2 = evaluate_job(caresource, self.config)
        self.assertEqual(ev2.location_bucket, "Remote-India")


if __name__ == "__main__":
    unittest.main()
