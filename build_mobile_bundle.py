"""Build a single self-contained offline HTML file for Android / Vivo 5G mobile usage."""

from __future__ import annotations

import json
from pathlib import Path
from server import build_jobs_payload

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DIST_DIR = ROOT / "dist"


def build_mobile_bundle() -> Path:
    """Inline CSS, JS, and scored jobs JSON into dist/job_radar_mobile.html."""
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    payload_json = json.dumps(build_jobs_payload(include_lan_ip=False), ensure_ascii=False)

    html = html.replace('<link rel="manifest" href="./manifest.json" />', "")
    html = html.replace('<link rel="icon" type="image/png" href="./icon-192.png" />', "")
    html = html.replace('<link rel="stylesheet" href="./styles.css" />', f"<style>\n{css}\n</style>")
    html = html.replace(
        '<script id="embedded-data" type="application/json">null</script>',
        f'<script id="embedded-data" type="application/json">{payload_json}</script>',
    )
    html = html.replace('<script src="./app.js"></script>', f"<script>\n{js}\n</script>")

    out_path = DIST_DIR / "job_radar_mobile.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    output = build_mobile_bundle()
    print(f"Built standalone mobile bundle: {output} ({output.stat().st_size} bytes)")
