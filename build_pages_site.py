"""Build both the GitHub Pages PWA directory (docs/) and offline mobile bundle."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from build_mobile_bundle import build_mobile_bundle
from server import build_jobs_payload

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DOCS_DIR = ROOT / "docs"

STATIC_FILES = (
    "index.html",
    "styles.css",
    "app.js",
    "manifest.json",
    "sw.js",
    "icon-192.png",
    "icon-512.png",
)


def build_pages_site() -> Path:
    """Publish privacy-safe GitHub Pages PWA assets and scored JSON payload into docs/."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    data_dir = DOCS_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    for filename in STATIC_FILES:
        src = WEB_DIR / filename
        if src.exists():
            shutil.copy2(src, DOCS_DIR / filename)

    # Never publish local PC LAN IP or personal PDFs to GitHub Pages
    payload = build_jobs_payload(include_lan_ip=False)
    payload_path = data_dir / "jobs_payload.json"
    payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    # Also keep offline standalone bundle synced
    build_mobile_bundle()
    return DOCS_DIR


if __name__ == "__main__":
    out_dir = build_pages_site()
    print(f"Built GitHub Pages PWA site in: {out_dir}")
