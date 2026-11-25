"""Job normalization, weighted fit scoring, and interview-safety evaluator."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "profile_config.json"


@dataclass
class JobEvaluation:
    """Evaluated job record normalized across job portals."""

    job_id: str
    source: str
    title: str
    company: str
    location: str
    work_mode: str
    exp_min: float | None
    exp_max: float | None
    salary_text: str | None
    salary_min_lpa: float | None
    salary_max_lpa: float | None
    salary_ok: bool | None
    posted_text: str | None
    url: str
    description: str
    skills_listed: list[str] = field(default_factory=list)
    fit_score: float = 0.0
    fit_breakdown: dict[str, float] = field(default_factory=dict)
    interview_risk: str = "LOW"
    risk_triggers: list[str] = field(default_factory=list)
    location_bucket: str = "India-Onsite/Hybrid"
    notice_compatible: bool = True
    notice_warning: str | None = None
    education_warning: str | None = None
    recommended_resume: str = "Track B (Operations & Process Excellence)"
    matched_proof_points: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
    rejected_reason: str | None = None
    tailored_pitch: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize evaluation to a JSON-compatible dictionary."""
        return asdict(self)


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    """Load profile configuration JSON."""
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with cfg_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def parse_experience_range(text: str) -> tuple[float | None, float | None]:
    """Extract min and max years of experience from strings like '3-6 Yrs' or '4+ years'."""
    if not text:
        return None, None
    cleaned = text.lower()
    range_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:-|to|–|—)\s*(\d+(?:\.\d+)?)\s*(?:yrs?|years?)",
        cleaned,
    )
    if range_match:
        return float(range_match.group(1)), float(range_match.group(2))

    plus_match = re.search(r"(\d+(?:\.\d+)?)\s*\+\s*(?:yrs?|years?)", cleaned)
    if plus_match:
        val = float(plus_match.group(1))
        return val, val + 3.0

    min_match = re.search(
        r"(?:minimum|min\.?|at\s+least)\s*(\d+(?:\.\d+)?)\s*(?:yrs?|years?)",
        cleaned,
    )
    if min_match:
        val = float(min_match.group(1))
        return val, val + 3.0

    return None, None


def parse_salary_lpa(salary_text: str | None, combined_text: str = "") -> tuple[float | None, float | None, bool]:
    """Parse INR LPA or USD salary and evaluate against ₹9 LPA floor."""
    # Only scan salary_text for USD to avoid matching revenue/GMV figures like '$300M+ transactions'
    usd_source = (salary_text or "").strip()
    if usd_source:
        usd_lower = usd_source.lower()
        usd_match = re.search(
            r"\$\s*(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?k)\s*(?:-|to|–)?\s*(?:\$\s*(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?k))?",
            usd_lower,
        )
        if usd_match and not re.search(r"\$\s*\d+(?:\.\d+)?\s*[mb]\b", usd_lower):
            def _parse_usd(raw: str) -> float:
                raw = raw.replace(",", "")
                if raw.endswith("k"):
                    return float(raw[:-1]) * 1000.0
                val = float(raw)
                return val * 1000.0 if val < 500 else val

            u_min = _parse_usd(usd_match.group(1))
            u_max = _parse_usd(usd_match.group(2)) if usd_match.group(2) else u_min
            lpa_min = round((u_min * 84.0) / 100000.0, 1)
            lpa_max = round((u_max * 84.0) / 100000.0, 1)
            return lpa_min, lpa_max, True

    source = (salary_text or "") + " " + combined_text
    if not source.strip():
        return None, None, False
    lowered = source.lower()

    inr_range = re.search(
        r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lacs?\s*(?:pa)?|lakhs?)",
        lowered,
    )
    if inr_range:
        return float(inr_range.group(1)), float(inr_range.group(2)), False

    inr_single = re.search(
        r"(?:₹|rs\.?|inr)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lacs?\s*(?:pa)?|lakhs?|l\b)",
        lowered,
    )
    if inr_single:
        val = float(inr_single.group(1))
        return val, val, False

    return None, None, False


def classify_location(location: str, work_mode: str, description: str) -> str:
    """Bucket job into Remote-Global, Remote-India, Overseas-Sponsored, or India-Onsite/Hybrid."""
    blob = f"{location} {work_mode} {description}".lower()
    sponsored_terms = (
        "visa sponsor", "relocation", "sponsorship", "work permit",
        "dubai", "uae", "united arab emirates", "singapore", "germany",
        "netherlands", "uk", "london", "ireland", "europe"
    )
    remote_flag = "remote" in blob or "work from home" in blob or "wfh" in blob or "anywhere" in blob
    india_cities = (
        "india", "ahmedabad", "bengaluru", "bangalore", "pune", "mumbai",
        "gurgaon", "gurugram", "noida", "delhi", "hyderabad", "chennai"
    )
    has_india = any(city in blob for city in india_cities)
    has_sponsored = any(term in blob for term in sponsored_terms)

    if has_sponsored and not has_india:
        return "Overseas-Sponsored"
    if remote_flag and (
        re.search(r"\b(global|worldwide|anywhere|usd|emea|usa|us)\b", blob)
        and not has_india
    ):
        return "Remote-Global"
    if remote_flag:
        return "Remote-India"
    if has_sponsored:
        return "Overseas-Sponsored"
    return "India-Onsite/Hybrid"


def evaluate_interview_safety(combined_text: str, config: dict[str, Any]) -> tuple[str, list[str]]:
    """Evaluate interview risk for a non-coding, non-formal-BA candidate."""
    lowered = combined_text.lower()
    rules = config.get("interview_risk_rules", {})
    triggers: list[str] = []

    high_hits = 0
    for rule in rules.get("high_risk", []):
        if _term_present(rule["term"], lowered):
            triggers.append(f"HIGH: {rule['reason']} ('{rule['term']}')")
            high_hits += 1

    med_hits = 0
    for rule in rules.get("medium_risk", []):
        if _term_present(rule["term"], lowered):
            triggers.append(f"MEDIUM: {rule['reason']} ('{rule['term']}')")
            med_hits += 1

    if high_hits >= 1 or med_hits >= 4:
        return "HIGH", triggers
    if med_hits >= 1:
        return "MEDIUM", triggers
    return "LOW", triggers


def _term_present(term: str, text_lower: str) -> bool:
    escaped = re.escape(term.lower())
    if term.isalpha():
        return bool(re.search(rf"\b{escaped}\b", text_lower))
    return term.lower() in text_lower


def _group_coverage(terms: list[str], text_lower: str, cap: int) -> tuple[float, list[str]]:
    matched = [t for t in terms if _term_present(t, text_lower)]
    ratio = min(1.0, len(matched) / max(1, cap))
    return ratio, matched


def _build_tailored_pitch(
    title: str,
    company: str,
    recommended_resume: str,
    proof_points: list[str],
) -> str:
    top_proof = proof_points[0] if proof_points else (
        "automated workflows saving 500+ manual hrs/month (Leonidas Award 2024) and cut launch SLAs by 50%."
    )
    angle = (
        "AI-enabled workflow prototyping and rapid operational execution"
        if "Track A" in recommended_resume
        else "operations optimization, SLA governance, and IT-partnered automation"
    )
    return (
        f"Hi Hiring Team at {company} — I am reaching out regarding the {title} opening. "
        f"With 4+ years across e-commerce and advertising operations (Ergode IT Services & TTEC/Rakuten), "
        f"my focus is {angle}. Highlight: {top_proof} "
        f"I would love to share how I can drive measurable efficiency in this role (60-day notice, open to discussion)."
    )


def evaluate_job(raw: dict[str, Any], config: dict[str, Any] | None = None) -> JobEvaluation:
    """Normalize a raw portal record and score it against Abhishek Dubey's real strengths."""
    cfg = config or load_config()
    title = str(raw.get("title") or raw.get("job_title") or "Untitled Role").strip()
    company = str(raw.get("company") or raw.get("company_name") or "Unknown Company").strip()
    location = str(raw.get("location") or raw.get("job_location") or "").strip()
    work_mode = str(raw.get("work_mode") or "Unspecified").strip()
    description = str(raw.get("description") or raw.get("job_summary") or "").strip()
    skills_listed = [str(s).strip() for s in (raw.get("skills_listed") or []) if str(s).strip()]
    salary_text = raw.get("salary_text")
    posted_text = raw.get("posted_text")
    url = str(raw.get("url") or "").strip()
    raw_source = str(raw.get("source") or "web").strip().lower()
    if "naukri" in raw_source:
        source = "naukri"
    elif "wellfound" in raw_source:
        source = "wellfound"
    elif "instahyre" in raw_source:
        source = "instahyre"
    elif "glassdoor" in raw_source:
        source = "glassdoor"
    elif "linkedin" in raw_source:
        source = "linkedin"
    else:
        source = raw_source
    job_id = str(raw.get("job_id") or f"{source}_{abs(hash((title, company, url))) % 10**8}")

    combined = f"{title} {company} {location} {work_mode} {' '.join(skills_listed)} {description}"
    lowered = combined.lower()

    exp_min = raw.get("exp_min")
    exp_max = raw.get("exp_max")
    if exp_min is None and exp_max is None:
        exp_min, exp_max = parse_experience_range(f"{raw.get('experience_text', '')} {description}")

    sal_min_lpa, sal_max_lpa, is_usd = parse_salary_lpa(salary_text, description)
    floor_lpa = float(cfg["candidate"]["floor_ctc_lpa"])
    salary_ok: bool | None = None
    if sal_max_lpa is not None:
        salary_ok = sal_max_lpa >= floor_lpa
    elif sal_min_lpa is not None:
        salary_ok = sal_min_lpa >= floor_lpa

    location_bucket = classify_location(location, work_mode, description)
    if work_mode == "Unspecified" and location_bucket.startswith("Remote"):
        work_mode = "Remote"

    notice_compatible = True
    notice_warning = None
    for pat in cfg.get("immediate_joiner_patterns", []):
        if pat in lowered:
            notice_compatible = False
            notice_warning = f"Contains '{pat}' — conflicts with 60-day notice period"
            break

    education_warning = None
    if re.search(r"(?:strictly\s+requires?|mandatory|must\s+have).*(?:\bb\.?e\.?/b\.?tech\b|\bb\.?tech\b|\bfull-time\s+mba\b)", lowered):
        education_warning = "JD states B.Tech/MBA requirement (candidate holds B.Com)"
    elif re.search(r"\bb\.?e\.?/b\.?tech\b", lowered) or (re.search(r"\bmba\b", lowered) and "preferred" in lowered):
        education_warning = "JD prefers/notes B.Tech or MBA (verify flexibility)"

    # Hard title + domain rejection check (blocks Web Developer, Forward Deployed Engineer, Account Executive, Acme)
    title_lower = title.lower()
    title_reject_hits = [
        term for term in cfg.get("title_reject_terms", []) if _term_present(term, title_lower)
    ]
    hard_hits = [term for term in cfg.get("hard_reject_keywords", []) if _term_present(term, lowered)]
    rejected_reason: str | None = None
    if title_reject_hits:
        rejected_reason = f"Title mismatch ({', '.join(title_reject_hits[:2])})"
    elif hard_hits:
        rejected_reason = f"Domain mismatch ({', '.join(hard_hits[:3])})"

    title_allow_hits = [
        term for term in cfg.get("title_allow_terms", []) if _term_present(term, title_lower)
    ]

    interview_risk, risk_triggers = evaluate_interview_safety(combined, cfg)

    kw_groups = cfg["keyword_groups"]

    ops_ratio, ops_hits = _group_coverage(kw_groups["operations_process"], lowered, cap=4)
    ai_ratio, ai_hits = _group_coverage(kw_groups["ai_workflow_automation"], lowered, cap=3)
    dom_ratio, dom_hits = _group_coverage(kw_groups["domain_ecommerce_adtech"], lowered, cap=2)

    # Dual-pillar role alignment (55 pts): strongest pillar (Ops or AI) + cross-pillar bonus
    primary_pts = max(ops_ratio, ai_ratio) * 40.0
    secondary_pts = min(ops_ratio, ai_ratio) * 15.0
    ops_pts = round(ops_ratio * 35.0, 1)
    ai_pts = round(ai_ratio * 25.0, 1)
    dom_pts = round(dom_ratio * 20.0, 1)

    # Logistics score (25 pts): experience + location + notice + salary floor
    logistics_score = 0.0
    cand_exp = float(cfg["candidate"]["experience_years"])
    if exp_min is not None and exp_max is not None:
        if exp_min - 0.5 <= cand_exp <= exp_max + 1.0:
            logistics_score += 10.0
        elif exp_min <= cand_exp + 1.5:
            logistics_score += 5.0
    else:
        logistics_score += 6.0

    if location_bucket in ("Remote-Global", "Remote-India", "Overseas-Sponsored"):
        logistics_score += 8.0
    else:
        logistics_score += 6.0

    if notice_compatible:
        logistics_score += 4.0
    if salary_ok is True or salary_ok is None:
        logistics_score += 3.0

    log_pts = round(min(25.0, logistics_score), 1)
    raw_score = primary_pts + secondary_pts + dom_pts + log_pts
    if title_allow_hits:
        raw_score += 8.0
    else:
        raw_score = max(0.0, raw_score - 20.0)

    if rejected_reason:
        raw_score = min(raw_score, 15.0)
    elif salary_ok is False:
        raw_score = max(0.0, raw_score - 25.0)
    if interview_risk == "HIGH":
        raw_score = max(0.0, raw_score - 20.0)
    elif interview_risk == "MEDIUM":
        raw_score = max(0.0, raw_score - 5.0)
    if not notice_compatible:
        raw_score = max(0.0, raw_score - 12.0)
    if education_warning and "strictly" in education_warning.lower() or (education_warning and "requirement" in education_warning.lower()):
        raw_score = max(0.0, raw_score - 15.0)
    elif education_warning:
        raw_score = max(0.0, raw_score - 5.0)

    fit_score = round(min(100.0, max(0.0, raw_score)), 1)

    # Route Track A vs Track B
    track_a_hits = sum(1 for k in cfg["tracks"]["track_a"]["boost_keywords"] if _term_present(k, lowered))
    track_b_hits = sum(1 for k in cfg["tracks"]["track_b"]["boost_keywords"] if _term_present(k, lowered))
    if track_a_hits > track_b_hits or location_bucket == "Remote-Global":
        recommended_resume = cfg["tracks"]["track_a"]["label"]
    else:
        recommended_resume = cfg["tracks"]["track_b"]["label"]

    # Matched Proof Points
    proofs: list[str] = []
    for item in cfg.get("proof_point_library", []):
        hits = sum(1 for trig in item["triggers"] if _term_present(trig, lowered))
        if hits >= 1:
            proofs.append((hits, item["story"]))
    proofs.sort(key=lambda x: x[0], reverse=True)
    matched_proof_points = [story for _, story in proofs[:3]]

    all_matched_kw = list(dict.fromkeys(ops_hits + ai_hits + dom_hits))
    pitch = _build_tailored_pitch(title, company, recommended_resume, matched_proof_points)

    return JobEvaluation(
        job_id=job_id,
        source=source,
        title=title,
        company=company,
        location=location or ("Remote" if location_bucket.startswith("Remote") else "India"),
        work_mode=work_mode,
        exp_min=exp_min,
        exp_max=exp_max,
        salary_text=salary_text or ("USD Remote" if is_usd else None),
        salary_min_lpa=sal_min_lpa,
        salary_max_lpa=sal_max_lpa,
        salary_ok=salary_ok,
        posted_text=posted_text,
        url=url,
        description=description,
        skills_listed=skills_listed,
        fit_score=fit_score,
        fit_breakdown={
            "operations_process": ops_pts,
            "ai_workflow_automation": ai_pts,
            "domain_ecommerce_adtech": dom_pts,
            "logistics_location_notice": log_pts,
        },
        interview_risk=interview_risk,
        risk_triggers=risk_triggers,
        location_bucket=location_bucket,
        notice_compatible=notice_compatible,
        notice_warning=notice_warning,
        education_warning=education_warning,
        recommended_resume=recommended_resume,
        matched_proof_points=matched_proof_points,
        matched_keywords=all_matched_kw,
        rejected_reason=rejected_reason,
        tailored_pitch=pitch,
    )


def deduplicate_and_score(raw_jobs: list[dict[str, Any]], config: dict[str, Any] | None = None) -> list[JobEvaluation]:
    """Evaluate raw jobs, deduplicate by normalized (company, title), and sort best-first."""
    cfg = config or load_config()
    seen: dict[tuple[str, str], JobEvaluation] = {}
    for raw in raw_jobs:
        ev = evaluate_job(raw, cfg)
        key = (
            re.sub(r"[^a-z0-9]", "", ev.company.lower()),
            re.sub(r"[^a-z0-9]", "", ev.title.lower()),
        )
        existing = seen.get(key)
        if existing is None or ev.fit_score > existing.fit_score:
            seen[key] = ev

    risk_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    results = list(seen.values())
    results.sort(
        key=lambda j: (
            1 if j.rejected_reason is None else 0,
            -risk_rank.get(j.interview_risk, 1),
            j.fit_score,
        ),
        reverse=True,
    )
    return results
