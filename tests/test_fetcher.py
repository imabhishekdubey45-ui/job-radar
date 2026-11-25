"""Tests for public API job fetcher, filters, and GitHub Pages PWA builder."""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from build_pages_site import build_pages_site  # noqa: E402
from fetch_jobs import (  # noqa: E402
    fetch_all_sources,
    filter_relevant_live_jobs,
    normalize_arbeitnow,
    normalize_himalayas,
    normalize_jobicy,
    strip_html,
)
from scorer import load_config  # noqa: E402


class FetcherAndPagesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(ROOT / "profile_config.json")

    def test_strip_html_cleans_markup(self) -> None:
        raw = "<p>Manage <strong>operations</strong> &amp; SLA workflows.<br>Excel required.</p>"
        self.assertEqual(strip_html(raw), "Manage operations & SLA workflows. Excel required.")

    def test_normalize_arbeitnow_and_english_filter(self) -> None:
        payload = {
            "data": [
                {
                    "slug": "ops-lead-berlin",
                    "company_name": "EuroScale GmbH",
                    "title": "Operations & Process Improvement Lead",
                    "description": "<p>Improve workflows, SOPs, and automation with cross-functional teams and visa sponsorship.</p>",
                    "remote": False,
                    "location": "Berlin",
                    "tags": ["Operations", "Process Improvement"],
                    "url": "https://arbeitnow.example/ops-lead",
                },
                {
                    "slug": "german-only-dev",
                    "company_name": "Berlin GmbH",
                    "title": "Softwareentwickler Python",
                    "description": "<p>Wir suchen einen Entwickler mit Python Erfahrung.</p>",
                    "remote": False,
                    "location": "Berlin",
                    "tags": ["Python"],
                    "url": "https://arbeitnow.example/de-dev",
                },
            ]
        }
        norm = normalize_arbeitnow(payload)
        self.assertEqual(len(norm), 2)
        kept = filter_relevant_live_jobs(norm, self.config)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["company"], "EuroScale GmbH")

    def test_normalize_himalayas_filters_us_only_keeps_worldwide(self) -> None:
        payload = {
            "jobs": [
                {
                    "title": "AI Operations Specialist",
                    "companyName": "GlobalFlow",
                    "description": "<p>Automate workflows and SOPs with Claude and Monday.com for remote operations teams.</p>",
                    "minSalary": 35000,
                    "maxSalary": 50000,
                    "currency": "USD",
                    "locationRestrictions": ["Worldwide"],
                    "applicationLink": "https://himalayas.example/global-ops",
                },
                {
                    "title": "Operations Manager",
                    "companyName": "USLocal Inc",
                    "description": "<p>Manage operations and SLA processes for US teams.</p>",
                    "locationRestrictions": ["United States"],
                    "applicationLink": "https://himalayas.example/us-only",
                },
            ]
        }
        norm = normalize_himalayas(payload)
        self.assertEqual(len(norm), 1)
        self.assertEqual(norm[0]["company"], "GlobalFlow")
        self.assertIn("$35,000 - $50,000", norm[0]["salary_text"])

    def test_normalize_jobicy_filters_usa_only(self) -> None:
        payload = {
            "jobs": [
                {
                    "id": 101,
                    "jobTitle": "Process Improvement &amp; RevOps Lead",
                    "companyName": "SaaSOps Co",
                    "jobGeo": "Anywhere",
                    "annualSalaryMin": "30000",
                    "annualSalaryMax": "42000",
                    "salaryCurrency": "USD",
                    "jobDescription": "<p>Lead workflow automation, CRM ops, and e-commerce onboarding for global teams.</p>",
                    "url": "https://jobicy.example/101",
                },
                {
                    "id": 102,
                    "jobTitle": "Operations Manager",
                    "companyName": "America Corp",
                    "jobGeo": "USA Only",
                    "jobDescription": "<p>Operations management for domestic hubs.</p>",
                    "url": "https://jobicy.example/102",
                },
            ]
        }
        norm = normalize_jobicy(payload)
        self.assertEqual(len(norm), 1)
        self.assertEqual(norm[0]["title"], "Process Improvement & RevOps Lead")

    def test_fetch_all_sources_handles_partial_api_failure(self) -> None:
        himalayas_ok = {
            "jobs": [
                {
                    "title": "Operations & Workflow Automation Lead",
                    "companyName": "ResilientCo",
                    "description": "<p>Build AI-assisted workflow automation, SOPs, and Monday.com dashboards for remote operations.</p>",
                    "minSalary": 30000,
                    "maxSalary": 40000,
                    "currency": "USD",
                    "locationRestrictions": ["Worldwide"],
                    "applicationLink": "https://himalayas.example/resilient",
                }
            ]
        }

        def fake_get(url: str, timeout: int = 20):
            if "himalayas.app" in url:
                return himalayas_ok
            raise TimeoutError("Simulated API timeout")

        with patch("fetch_jobs._http_get_json", side_effect=fake_get):
            jobs, log = fetch_all_sources(self.config)

        self.assertEqual(len(jobs), 1)
        self.assertIn("skipped", log["arbeitnow"])
        self.assertIn("ok", log["himalayas"])
        self.assertIn("skipped", log["jobicy"])

    def test_build_pages_site_outputs_privacy_safe_pwa(self) -> None:
        docs_dir = build_pages_site()
        for req_file in ("index.html", "styles.css", "app.js", "manifest.json", "sw.js", "icon-192.png", "icon-512.png"):
            self.assertTrue((docs_dir / req_file).exists(), f"Missing {req_file} in docs/")

        payload_file = docs_dir / "data" / "jobs_payload.json"
        self.assertTrue(payload_file.exists())
        payload = json.loads(payload_file.read_text(encoding="utf-8"))
        self.assertNotIn("lan_ip", payload)
        self.assertGreaterEqual(len(payload["jobs"]), 26)
        raw_text = payload_file.read_text(encoding="utf-8")
        self.assertNotRegex(raw_text, r"\+91[- ]?\d{10}")
        self.assertNotRegex(raw_text, r"[a-z0-9_.+-]+@gmail\.com")


if __name__ == "__main__":
    unittest.main()
