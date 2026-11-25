"""Local HTTP server for the mobile-first Job Radar Workbench."""

from __future__ import annotations

import argparse
import csv
import io
import json
import socket
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from scorer import deduplicate_and_score, evaluate_job, load_config

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
DATA_DIR = ROOT / "data"
RESUMES_OUT_DIR = ROOT / "resumes" / "output"
JOBS_FILE = DATA_DIR / "jobs_raw.json"
META_FILE = DATA_DIR / "jobs_meta.json"
TRACKER_FILE = DATA_DIR / "tracker_state.json"

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".pdf": "application/pdf",
}


def get_lan_ip() -> str:
    """Return local Wi-Fi IPv4 address for mobile device access on the same network."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


def build_jobs_payload(include_lan_ip: bool = True) -> dict[str, Any]:
    """Load, score, deduplicate, and merge tracker state with raw jobs."""
    config = load_config(ROOT / "profile_config.json")
    raw_jobs = _read_json(JOBS_FILE, [])
    meta = _read_json(META_FILE, {})
    tracker = _read_json(TRACKER_FILE, {})
    evaluated = deduplicate_and_score(raw_jobs, config)
    items = []
    for ev in evaluated:
        rec = ev.to_dict()
        rec["status"] = tracker.get(ev.job_id, "new")
        items.append(rec)
    payload: dict[str, Any] = {
        "jobs": items,
        "config": config,
        "meta": meta,
    }
    if include_lan_ip:
        payload["lan_ip"] = get_lan_ip()
    return payload


def export_jobs_csv() -> str:
    """Serialize scored jobs as RFC-4180 CSV string."""
    payload = build_jobs_payload()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "Job ID",
            "Title",
            "Company",
            "Source",
            "Location",
            "Location Bucket",
            "Work Mode",
            "Fit Score",
            "Interview Risk",
            "Recommended Resume",
            "Salary",
            "Notice Safe",
            "Status",
            "URL",
        ]
    )
    for j in payload["jobs"]:
        writer.writerow(
            [
                j["job_id"],
                j["title"],
                j["company"],
                j["source"],
                j["location"],
                j["location_bucket"],
                j["work_mode"],
                j["fit_score"],
                j["interview_risk"],
                j["recommended_resume"],
                j.get("salary_text") or "",
                "Yes" if j["notice_compatible"] else "No (Immediate Risk)",
                j["status"],
                j["url"],
            ]
        )
    return buf.getvalue()


class JobRadarHandler(BaseHTTPRequestHandler):
    """HTTP handler serving static mobile/desktop UI and JSON/CSV APIs."""

    server_port: int = 8765

    def log_message(self, format: str, *args: Any) -> None:
        return  # Keep server output clean

    def _send_bytes(self, status: int, content_type: str, body: bytes, extra_headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, data: Any) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, "application/json; charset=utf-8", raw)

    def _read_body_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/jobs":
            self._send_json(HTTPStatus.OK, build_jobs_payload())
            return

        if path == "/api/network-info":
            ip = get_lan_ip()
            self._send_json(
                HTTPStatus.OK,
                {
                    "lan_url": f"http://{ip}:{self.server_port}",
                    "local_url": f"http://localhost:{self.server_port}",
                },
            )
            return

        if path == "/api/export.csv":
            csv_bytes = export_jobs_csv().encode("utf-8-sig")
            self._send_bytes(
                HTTPStatus.OK,
                "text/csv; charset=utf-8",
                csv_bytes,
                {"Content-Disposition": 'attachment; filename="abhishek_job_radar.csv"'},
            )
            return

        if path.startswith("/resumes/"):
            filename = Path(path.replace("/resumes/", "", 1)).name
            target = (RESUMES_OUT_DIR / filename).resolve()
            if target.parent == RESUMES_OUT_DIR.resolve() and target.is_file():
                self._send_bytes(
                    HTTPStatus.OK,
                    "application/pdf",
                    target.read_bytes(),
                    {"Content-Disposition": f'inline; filename="{filename}"'},
                )
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Resume not found"})
            return

        rel = "index.html" if path == "/" else path.lstrip("/")
        target = (WEB_DIR / rel).resolve()
        if target.parent == WEB_DIR.resolve() and target.is_file():
            mime = MIME_TYPES.get(target.suffix.lower(), "application/octet-stream")
            self._send_bytes(HTTPStatus.OK, mime, target.read_bytes())
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        try:
            body = self._read_body_json()
        except Exception:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body"})
            return

        if path == "/api/status":
            job_id = str(body.get("job_id") or "").strip()
            status = str(body.get("status") or "new").strip().lower()
            if not job_id or status not in ("new", "shortlisted", "applied", "interviewing", "skip"):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid job_id or status"})
                return
            tracker = _read_json(TRACKER_FILE, {})
            tracker[job_id] = status
            _write_json(TRACKER_FILE, tracker)
            self._send_json(HTTPStatus.OK, {"ok": True, "job_id": job_id, "status": status})
            return

        if path == "/api/evaluate":
            config = load_config(ROOT / "profile_config.json")
            ev = evaluate_job(body, config)
            rec = ev.to_dict()
            rec["status"] = "new"
            if body.get("save"):
                raw_jobs = _read_json(JOBS_FILE, [])
                body_copy = dict(body)
                body_copy.setdefault("job_id", ev.job_id)
                body_copy.setdefault("source", "manual")
                raw_jobs.append(body_copy)
                _write_json(JOBS_FILE, raw_jobs)
            self._send_json(HTTPStatus.OK, rec)
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Endpoint not found"})


def run_server(host: str = "0.0.0.0", port: int = 8765) -> None:
    """Start multi-threaded HTTP server."""
    JobRadarHandler.server_port = port
    httpd = ThreadingHTTPServer((host, port), JobRadarHandler)
    lan_ip = get_lan_ip()
    print(f"Job Radar running at http://localhost:{port} (Vivo Wi-Fi URL: http://{lan_ip}:{port})")
    httpd.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Start Job Radar Workbench server.")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (0.0.0.0 for LAN/mobile)")
    parser.add_argument("--port", type=int, default=8765, help="Server port")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
