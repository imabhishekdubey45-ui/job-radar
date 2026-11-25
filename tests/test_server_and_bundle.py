"""Tests for server payload, CSV export, and standalone Vivo mobile bundle builder."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from build_mobile_bundle import build_mobile_bundle  # noqa: E402
from server import build_jobs_payload, export_jobs_csv  # noqa: E402


class ServerAndBundleTestCase(unittest.TestCase):
    def test_build_jobs_payload_returns_config(self) -> None:
        payload = build_jobs_payload()
        self.assertIn("jobs", payload)
        self.assertIn("config", payload)
        self.assertIn("lan_ip", payload)

    def test_export_jobs_csv_has_header(self) -> None:
        csv_text = export_jobs_csv()
        first_line = csv_text.splitlines()[0]
        self.assertIn("Job ID,Title,Company,Source", first_line)

    def test_mobile_bundle_embeds_valid_json_and_styles(self) -> None:
        out_path = build_mobile_bundle()
        self.assertTrue(out_path.exists())
        html = out_path.read_text(encoding="utf-8")
        self.assertIn("<style>", html)
        self.assertNotIn('href="./styles.css"', html)
        self.assertNotIn('src="./app.js"', html)
        marker = '<script id="embedded-data" type="application/json">'
        start = html.index(marker) + len(marker)
        end = html.index("</script>", start)
        parsed = json.loads(html[start:end])
        self.assertIn("jobs", parsed)
        self.assertIn("config", parsed)


if __name__ == "__main__":
    unittest.main()
