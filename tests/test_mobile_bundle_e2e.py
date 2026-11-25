"""End-to-end Playwright test verifying standalone Vivo offline bundle and GitHub Pages docs/ PWA."""

import functools
import http.server
import sys
import threading
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _launch_browser(p):
    for kw in ({"channel": "chrome"}, {"channel": "msedge"}):
        try:
            return p.chromium.launch(**kw)
        except Exception:
            continue
    return None


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        return


class MobileBundleE2ETestCase(unittest.TestCase):
    def test_offline_bundle_renders_and_evaluates_on_mobile(self) -> None:
        bundle = ROOT / "dist" / "job_radar_mobile.html"
        self.assertTrue(bundle.exists())
        errors: list[str] = []

        with sync_playwright() as p:
            browser = _launch_browser(p)
            self.assertIsNotNone(browser, "Chrome/Edge must be available")
            try:
                page = browser.new_page(viewport={"width": 390, "height": 844})
                page.on("pageerror", lambda err: errors.append(str(err)))
                page.goto(bundle.resolve().as_uri(), wait_until="load")

                self.assertEqual(page.locator("#modeBadge").inner_text(), "Vivo 5G Offline Mode")
                self.assertGreaterEqual(int(page.locator("#kpiTotal").inner_text()), 26)
                overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
                self.assertFalse(overflow, "Mobile layout should not overflow horizontally")

                page.locator('button.nav-btn[data-tab="evaluate"]').click()
                page.locator("#evalDemoAcmeBtn").click()
                eval_txt = page.locator("#evalResult").inner_text()
                self.assertIn("Rejected", eval_txt)
                self.assertIn("0%", eval_txt)

                page.locator('button.nav-btn[data-tab="profiles"]').click()
                self.assertGreaterEqual(page.locator(".snippet-card").count(), 5)
            finally:
                browser.close()

        self.assertEqual(errors, [], f"Unexpected page errors: {errors}")

    def test_github_pages_docs_pwa_renders_cloud_mode_on_mobile(self) -> None:
        docs_dir = ROOT / "docs"
        self.assertTrue((docs_dir / "index.html").exists())
        handler = functools.partial(_QuietHandler, directory=str(docs_dir))
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()

        errors: list[str] = []
        try:
            with sync_playwright() as p:
                browser = _launch_browser(p)
                self.assertIsNotNone(browser)
                try:
                    page = browser.new_page(viewport={"width": 390, "height": 844})
                    page.on("pageerror", lambda err: errors.append(str(err)))
                    page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")

                    self.assertEqual(page.locator("#modeBadge").inner_text(), "Cloud PWA")
                    self.assertGreaterEqual(int(page.locator("#kpiTotal").inner_text()), 26)
                    overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
                    self.assertFalse(overflow, "Cloud PWA mobile view should not overflow")

                    page.locator('button.nav-btn[data-tab="sync"]').click()
                    page.locator("#pullLatestBtn").click()
                    self.assertNotRegex(page.content(), r"@gmail\.com")
                finally:
                    browser.close()
        finally:
            httpd.shutdown()
            httpd.server_close()

        self.assertEqual(errors, [], f"Unexpected Cloud PWA page errors: {errors}")


if __name__ == "__main__":
    unittest.main()
