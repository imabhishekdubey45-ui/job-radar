"""Fetch live global remote & visa-sponsored operations jobs from free public APIs."""

from __future__ import annotations

import argparse
import html
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scorer import deduplicate_and_score, evaluate_job, load_config

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SEED_FILE = DATA_DIR / "jobs_seed.json"
RAW_FILE = DATA_DIR / "jobs_raw.json"
META_FILE = DATA_DIR / "jobs_meta.json"

ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api?page={page}"
HIMALAYAS_URLS = (
    "https://himalayas.app/jobs/api/search?q=operations&worldwide=true",
    "https://himalayas.app/jobs/api/search?q=process+improvement&worldwide=true",
    "https://himalayas.app/jobs/api/search?q=workflow+automation&worldwide=true",
    "https://himalayas.app/jobs/api?limit=50",
)
JOBICY_URLS = (
    "https://jobicy.com/api/v2/remote-jobs?count=50&geo=anywhere",
    "https://jobicy.com/api/v2/remote-jobs?count=50&geo=apac",
)

USER_AGENT = "JobRadarBot/1.0 (+https://github.com)"

ELIGIBLE_GEO_TOKENS = ("worldwide", "anywhere", "global", "india", "apac", "asia", "all regions")


def strip_html(raw_html: str | None) -> str:
    """Convert HTML snippet to clean single-spaced plain text."""
    if not raw_html:
        return ""
    text = re.sub(r"<(br|p|li|div|h[1-6])[^>]*>", " ", raw_html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _http_get_json(url: str, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return json.loads(resp.read().decode(charset, errors="replace"))


def _is_geo_eligible(geo_text: str, restrictions: list[str] | None = None, has_visa_sponsor: bool = False) -> bool:
    """Allowload only Worldwide/Anywhere/Global/India/APAC remote roles or explicit visa sponsorship."""
    if has_visa_sponsor:
        return True
    tokens = [t.strip().lower() for t in re.split(r"[,;/|]+", geo_text or "") if t.strip()]
    if restrictions:
        tokens.extend(r.strip().lower() for r in restrictions if r and r.strip())
    if not tokens:
        return True
    return any(allowed in tok for tok in tokens for allowed in ELIGIBLE_GEO_TOKENS)


def normalize_arbeitnow(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize Arbeitnow API response (Europe / Visa-Sponsored / Remote)."""
    records = payload.get("data") if isinstance(payload, dict) else []
    if not isinstance(records, list):
        return []
    out: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        company = str(item.get("company_name") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title or not url:
            continue
        desc = strip_html(item.get("description"))
        tags = [str(t) for t in (item.get("tags") or []) if t]
        loc = str(item.get("location") or "Europe").strip()
        is_remote = bool(item.get("remote"))
        desc_lower = desc.lower()
        has_visa = any(
            k in desc_lower for k in ("visa sponsor", "visa support", "relocation package", "relocation support", "work permit")
        )
        has_global_remote = is_remote and any(
            k in desc_lower for k in ("worldwide", "anywhere", "global", "work from anywhere", "india")
        )
        # Skip local European roles that neither sponsor visas nor hire globally remote
        if not has_visa and not has_global_remote:
            continue
        work_mode = "Remote" if has_global_remote else "Overseas Visa-Sponsored"
        out.append(
            {
                "job_id": f"arbeitnow_{item.get('slug') or abs(hash(url)) % 10**8}",
                "source": "arbeitnow",
                "title": title,
                "company": company or "European Employer",
                "location": f"{loc} (Remote)" if is_remote and "remote" not in loc.lower() else loc,
                "work_mode": work_mode,
                "experience_text": "",
                "salary_text": None,
                "posted_text": "Live API",
                "skills_listed": tags[:10],
                "description": desc[:2500],
                "url": url,
            }
        )
    return out


def normalize_himalayas(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize Himalayas Remote Jobs API response."""
    records = payload.get("jobs") if isinstance(payload, dict) else []
    if not isinstance(records, list):
        return []
    out: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("applicationLink") or item.get("guid") or "").strip()
        if not title or not url:
            continue
        restrictions = [str(r) for r in (item.get("locationRestrictions") or []) if r]
        if not _is_geo_eligible("", restrictions):
            continue

        min_sal = item.get("minSalary")
        max_sal = item.get("maxSalary")
        curr = str(item.get("currency") or "USD").strip()
        salary_text = None
        if min_sal and max_sal:
            salary_text = f"${int(min_sal):,} - ${int(max_sal):,} / year" if curr == "USD" else f"{curr} {min_sal}-{max_sal}"
        elif max_sal:
            salary_text = f"Up to ${int(max_sal):,} / year" if curr == "USD" else f"Up to {curr} {max_sal}"

        desc = strip_html(item.get("description") or item.get("excerpt"))
        loc_label = ", ".join(restrictions) if restrictions else "Remote (Worldwide)"
        seniority = item.get("seniority") or []
        categories = item.get("categories") or []
        out.append(
            {
                "job_id": f"himalayas_{abs(hash((title, item.get('companyName'), url))) % 10**9}",
                "source": "himalayas",
                "title": title,
                "company": str(item.get("companyName") or "Remote Company").strip(),
                "location": f"Remote ({loc_label})" if "remote" not in loc_label.lower() else loc_label,
                "work_mode": "Remote",
                "experience_text": ", ".join(seniority) if isinstance(seniority, list) else str(seniority),
                "salary_text": salary_text,
                "posted_text": "Live API",
                "skills_listed": [str(c) for c in categories[:8]] if isinstance(categories, list) else [],
                "description": desc[:2500],
                "url": url,
            }
        )
    return out


def normalize_jobicy(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize Jobicy v2 Remote Jobs API response."""
    records = payload.get("jobs") if isinstance(payload, dict) else []
    if not isinstance(records, list):
        return []
    out: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        title = html.unescape(str(item.get("jobTitle") or "").strip())
        url = str(item.get("url") or "").strip()
        if not title or not url:
            continue
        geo = str(item.get("jobGeo") or "Anywhere").strip()
        if not _is_geo_eligible(geo):
            continue

        s_min = item.get("annualSalaryMin")
        s_max = item.get("annualSalaryMax")
        curr = str(item.get("salaryCurrency") or "USD").strip()
        salary_text = None
        if s_min and s_max:
            salary_text = f"${s_min} - ${s_max} / year" if curr == "USD" else f"{curr} {s_min}-{s_max}"

        desc = strip_html(item.get("jobDescription") or item.get("jobExcerpt"))
        industries = item.get("jobIndustry") or []
        skills = [html.unescape(str(x)) for x in industries[:8]] if isinstance(industries, list) else []
        out.append(
            {
                "job_id": f"jobicy_{item.get('id') or abs(hash(url)) % 10**8}",
                "source": "jobicy",
                "title": title,
                "company": html.unescape(str(item.get("companyName") or "Remote Company").strip()),
                "location": f"Remote ({geo})",
                "work_mode": "Remote",
                "experience_text": str(item.get("jobLevel") or ""),
                "salary_text": salary_text,
                "posted_text": str(item.get("pubDate") or "Recent")[:10],
                "skills_listed": skills,
                "description": desc[:2500],
                "url": url,
            }
        )
    return out


def _looks_english(text: str) -> bool:
    lowered = f" {text.lower()} "
    english_markers = (" and ", " the ", " with ", " for ", " to ", " in ", " of ")
    return sum(1 for m in english_markers if m in lowered) >= 2


def _title_matches_target(title: str, config: dict[str, Any]) -> bool:
    title_lower = title.lower()
    allow = config.get("title_allow_terms", [])
    return any(
        bool(re.search(rf"\b{re.escape(t)}\b", title_lower)) if len(t) <= 4 and t.isalpha() else t in title_lower
        for t in allow
    )


def filter_relevant_live_jobs(candidates: list[dict[str, Any]], config: dict[str, Any], min_score: float = 55.0) -> list[dict[str, Any]]:
    """Keep only English, title-matched, interview-safe, high-fit live API matches."""
    kept: list[dict[str, Any]] = []
    for raw in candidates:
        title = str(raw.get("title") or "")
        desc = str(raw.get("description") or "")
        if not _looks_english(f"{title} {desc}"):
            continue
        if not _title_matches_target(title, config):
            continue
        ev = evaluate_job(raw, config)
        if ev.rejected_reason:
            continue
        if ev.interview_risk == "HIGH":
            continue
        core_pts = ev.fit_breakdown.get("operations_process", 0) + ev.fit_breakdown.get("ai_workflow_automation", 0)
        if core_pts < 14.0:
            continue
        if ev.fit_score >= min_score:
            kept.append(raw)
    return kept


def fetch_all_sources(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Query public JSON APIs defensively; individual source failures never break the run."""
    status_log: dict[str, str] = {}
    collected: list[dict[str, Any]] = []

    try:
        norm = []
        for page_num in (1, 2, 3):
            norm.extend(normalize_arbeitnow(_http_get_json(ARBEITNOW_URL.format(page=page_num))))
        kept = filter_relevant_live_jobs(norm, config)
        collected.extend(kept)
        status_log["arbeitnow"] = f"ok ({len(kept)}/{len(norm)} relevant)"
    except Exception as exc:
        status_log["arbeitnow"] = f"skipped ({exc})"

    him_norm: list[dict[str, Any]] = []
    him_errors: list[str] = []
    for h_url in HIMALAYAS_URLS:
        try:
            him_norm.extend(normalize_himalayas(_http_get_json(h_url)))
        except Exception as exc:
            him_errors.append(str(exc))
    if him_norm:
        kept = filter_relevant_live_jobs(him_norm, config)
        collected.extend(kept)
        status_log["himalayas"] = f"ok ({len(kept)}/{len(him_norm)} relevant)"
    else:
        status_log["himalayas"] = f"skipped ({'; '.join(him_errors[:1]) or 'no data'})"

    jcy_norm: list[dict[str, Any]] = []
    jcy_errors: list[str] = []
    for j_url in JOBICY_URLS:
        try:
            jcy_norm.extend(normalize_jobicy(_http_get_json(j_url)))
        except Exception as exc:
            jcy_errors.append(str(exc))
    if jcy_norm:
        kept = filter_relevant_live_jobs(jcy_norm, config)
        collected.extend(kept)
        status_log["jobicy"] = f"ok ({len(kept)}/{len(jcy_norm)} relevant)"
    else:
        status_log["jobicy"] = f"skipped ({'; '.join(jcy_errors[:1]) or 'no data'})"

    # Deduplicate across overlapping search queries (e.g. multiple Himalayas queries)
    deduped: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for item in collected:
        key = (
            re.sub(r"[^a-z0-9]", "", str(item.get("company") or "").lower()),
            re.sub(r"[^a-z0-9]", "", str(item.get("title") or "").lower()),
        )
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(item)

    return deduped, status_log


def merge_and_save(live_jobs: list[dict[str, Any]], status_log: dict[str, str], max_live_api: int = 25) -> dict[str, Any]:
    """Always preserve curated seed jobs and merge top-scored live API matches."""
    config = load_config(ROOT / "profile_config.json")
    seed_jobs: list[dict[str, Any]] = []
    if SEED_FILE.exists():
        seed_jobs = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    elif RAW_FILE.exists():
        seed_jobs = json.loads(RAW_FILE.read_text(encoding="utf-8"))

    # Rank live API candidates first and keep top max_live_api so seed jobs are never evicted
    scored_live = deduplicate_and_score(live_jobs, config)
    top_live_ids = {ev.job_id for ev in scored_live[:max_live_api]}
    filtered_live = [raw for raw in live_jobs if evaluate_job(raw, config).job_id in top_live_ids]

    combined_raw = seed_jobs + filtered_live
    scored_all = deduplicate_and_score(combined_raw, config)
    kept_ids = {ev.job_id for ev in scored_all}

    by_id: dict[str, dict[str, Any]] = {}
    for raw in combined_raw:
        ev = evaluate_job(raw, config)
        if ev.job_id in kept_ids and ev.job_id not in by_id:
            by_id[ev.job_id] = raw

    merged_list = list(by_id.values())
    RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
    RAW_FILE.write_text(json.dumps(merged_list, indent=2, ensure_ascii=False), encoding="utf-8")

    now_utc = datetime.now(timezone.utc)
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = now_utc.astimezone(ist_tz)
    meta = {
        "last_refreshed_utc": now_utc.strftime("%Y-%m-%d %H:%M UTC"),
        "last_refreshed_ist": now_ist.strftime("%d %b %Y, %I:%M %p IST"),
        "total_jobs": len(merged_list),
        "live_fetched_count": len(live_jobs),
        "seed_count": len(seed_jobs),
        "source_status": status_log,
    }
    META_FILE.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch live remote/visa-sponsored operations jobs.")
    parser.add_argument("--dry-run", action="store_true", help="Print counts without writing files.")
    args = parser.parse_args()

    config = load_config(ROOT / "profile_config.json")
    live_jobs, status_log = fetch_all_sources(config)
    print("Source status:", json.dumps(status_log))
    if args.dry_run:
        print(f"Dry run complete: {len(live_jobs)} relevant live jobs found.")
        return
    meta = merge_and_save(live_jobs, status_log)
    print("Updated jobs_raw.json:", json.dumps(meta))


if __name__ == "__main__":
    main()
