(() => {
  const PROFILE_SNIPPETS = [
    {
      title: "LinkedIn Headline (207 chars)",
      body: "Operations & Process Improvement Specialist | AI-Enabled Workflow Automation (Claude & No-Code) | E-Commerce & AdTech Ops | 50% Launch SLA Reduction • $50K+ Operational Recovery • 500+ Hrs/Mo Automated"
    },
    {
      title: "Naukri Resume Headline (243 chars)",
      body: "Operations & Process Improvement Specialist (4+ Yrs) | E-Commerce & AdTech Ops | AI-Assisted Workflows | Cut Launch SLA 50%, Recovered $50K+, Automated 500+ Hrs/Mo (Leonidas Award) | 60-Day Notice"
    },
    {
      title: "Wellfound / Startup Bio",
      body: "Operations & AI Workflow Builder (4+ Yrs | E-Commerce & AdTech). I diagnose messy ops bottlenecks and ship working workflows fast using AI tools (Claude/Antigravity) & IT collaboration—500+ hrs/mo saved (Leonidas Award), 50% launch SLA cut, $50K+ variance/inventory recovered, 50K-row matching shipped in 4 days."
    },
    {
      title: "LinkedIn About Summary",
      body: "I turn messy, manual operational bottlenecks into fast, scalable workflows with measurable ROI.\n\nOver 4+ years across e-commerce marketplaces (Ergode IT Services) and global digital advertising operations (TTEC supporting Rakuten Advertising), I focus on spotting where time or money is leaking, designing a practical process fix, and shipping it—either by partnering with IT or rapidly prototyping workflows using AI tools (Claude, Antigravity).\n\nHighlights: 500+ hrs/mo automated (Leonidas Award 2024) | $31K->$2.8K monthly variance cut + $20K Amazon recovery | 50% launch SLA reduction | 50K+ creator matching shipped in 4-5 days | Monday.com KPI dashboard & EU/APAC/US execution."
    },
    {
      title: "60-Second Interview Opener",
      body: "I'm an Operations & Process Improvement specialist with 4+ years across e-commerce marketplaces and digital advertising ops. My strength is spotting manual bottlenecks, designing practical logic/workflows, and getting working solutions shipped fast—either with IT or using AI tools like Claude and Antigravity. At Ergode I drove automation saving 500+ hrs/month (Leonidas Award) and cut rate variance from $31K to $2.8K; at TTEC I launched client intake in 1 month, cut SLAs by 50%, and built a 50K-row matching workflow in 4-5 days."
    },
    {
      title: "Naukri / LinkedIn Key Skills (Safe List)",
      body: "Process Improvement, Operations Management, Workflow Automation, AI Operations, Prompt Engineering, E-Commerce Operations, AdTech Operations, Vendor Onboarding, SLA Management, Root Cause Analysis, Variance Analysis, SOP Development, Monday.com, Salesforce CRM, Advanced Excel, Change Management, Jira, Confluence"
    }
  ];

  const state = {
    jobs: [],
    config: null,
    selectedId: null,
    offlineMode: false,
    localStatuses: {}
  };

  function safeGetStorage(key, fallback) {
    try {
      const raw = window.localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch {
      return fallback;
    }
  }

  function safeSetStorage(key, val) {
    try {
      window.localStorage.setItem(key, JSON.stringify(val));
    } catch {
      // Fallback safely in restricted Android content:// viewers
    }
  }

  function showToast(msg) {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(showToast._timer);
    showToast._timer = setTimeout(() => { el.hidden = true; }, 1900);
  }

  function escapeHtml(str) {
    return String(str || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function termPresent(term, textLower) {
    const t = term.toLowerCase();
    if (/^[a-z]+$/.test(t)) {
      const re = new RegExp(`\\b${t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i");
      return re.test(textLower);
    }
    return textLower.includes(t);
  }

  // Client-side scorer mirroring scorer.py so offline Vivo 5G Evaluate tab works natively
  function evaluateJobClient(raw, cfg) {
    const title = (raw.title || "Untitled Role").trim();
    const company = (raw.company || "Unknown Company").trim();
    const location = (raw.location || "").trim();
    const workMode = (raw.work_mode || "Unspecified").trim();
    const desc = (raw.description || "").trim();
    const salaryText = raw.salary_text || "";
    const combined = `${title} ${company} ${location} ${workMode} ${desc}`;
    const lowered = combined.toLowerCase();

    const titleLower = title.toLowerCase();
    const titleRejectHits = (cfg.title_reject_terms || []).filter(t => termPresent(t, titleLower));
    const hardHits = (cfg.hard_reject_keywords || []).filter(t => termPresent(t, lowered));
    let rejectedReason = null;
    if (titleRejectHits.length) {
      rejectedReason = `Title mismatch (${titleRejectHits.slice(0, 2).join(", ")})`;
    } else if (hardHits.length) {
      rejectedReason = `Domain mismatch (${hardHits.slice(0, 3).join(", ")})`;
    }
    const titleAllowHits = (cfg.title_allow_terms || []).filter(t => termPresent(t, titleLower));

    const rules = cfg.interview_risk_rules || {};
    const triggers = [];
    let highHits = 0;
    let medHits = 0;
    (rules.high_risk || []).forEach(r => {
      if (termPresent(r.term, lowered)) {
        triggers.push(`HIGH: ${r.reason} ('${r.term}')`);
        highHits += 1;
      }
    });
    (rules.medium_risk || []).forEach(r => {
      if (termPresent(r.term, lowered)) {
        triggers.push(`MEDIUM: ${r.reason} ('${r.term}')`);
        medHits += 1;
      }
    });
    const interviewRisk = (highHits >= 1 || medHits >= 4) ? "HIGH" : (medHits >= 1 ? "MEDIUM" : "LOW");

    const kw = cfg.keyword_groups || {};
    const opsHits = (kw.operations_process || []).filter(t => termPresent(t, lowered));
    const aiHits = (kw.ai_workflow_automation || []).filter(t => termPresent(t, lowered));
    const domHits = (kw.domain_ecommerce_adtech || []).filter(t => termPresent(t, lowered));

    const opsRatio = Math.min(1, opsHits.length / 4);
    const aiRatio = Math.min(1, aiHits.length / 3);
    const domRatio = Math.min(1, domHits.length / 2);

    const opsPts = Number((opsRatio * 35).toFixed(1));
    const aiPts = Number((aiRatio * 25).toFixed(1));
    const domPts = Number((domRatio * 20).toFixed(1));

    let locBucket = "India-Onsite/Hybrid";
    const hasIndia = /\b(india|ahmedabad|bengaluru|bangalore|pune|mumbai|gurgaon|gurugram|noida|delhi|hyderabad|chennai)\b/i.test(combined);
    if (/(visa sponsor|relocation|dubai|uae|europe|germany|singapore|uk|ireland)/i.test(combined) && !hasIndia) {
      locBucket = "Overseas-Sponsored";
    } else if (/remote|wfh|anywhere/i.test(combined)) {
      locBucket = (/\b(global|worldwide|anywhere|usd|emea|usa|us)\b/i.test(combined) && !hasIndia) ? "Remote-Global" : "Remote-India";
    }

    let noticeCompat = true;
    let noticeWarn = null;
    for (const p of (cfg.immediate_joiner_patterns || [])) {
      if (lowered.includes(p)) {
        noticeCompat = false;
        noticeWarn = `Contains '${p}' — conflicts with 60-day notice period`;
        break;
      }
    }

    let edWarn = null;
    if (/(strictly\s+requires?|mandatory|must\s+have).*(\bb\.?e\.?\/b\.?tech\b|\bb\.?tech\b|\bfull-time\s+mba\b)/i.test(lowered)) {
      edWarn = "JD states B.Tech/MBA requirement (candidate holds B.Com)";
    } else if (/\bb\.?e\.?\/b\.?tech\b/i.test(lowered) || (/\bmba\b/i.test(lowered) && lowered.includes("preferred"))) {
      edWarn = "JD prefers/notes B.Tech or MBA (verify flexibility)";
    }

    let salaryOk = null;
    const inrMatch = (salaryText + " " + desc).toLowerCase().match(/(\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lacs|lakhs)/);
    if (inrMatch) {
      salaryOk = parseFloat(inrMatch[2]) >= Number(cfg.candidate.floor_ctc_lpa || 9);
    } else if (/\$\s*\d/.test(salaryText) && !/\$\s*\d+(?:\.\d+)?\s*[mb]\b/i.test(salaryText)) {
      salaryOk = true;
    }

    let logPts = 6 + (locBucket.startsWith("Remote") || locBucket === "Overseas-Sponsored" ? 8 : 6) + (noticeCompat ? 4 : 0) + (salaryOk !== false ? 3 : 0);
    logPts = Math.min(25, logPts);

    let score = Math.max(opsRatio, aiRatio) * 40 + Math.min(opsRatio, aiRatio) * 15 + domPts + logPts;
    if (titleAllowHits.length) score += 8;
    else score = Math.max(0, score - 20);
    if (rejectedReason) score = Math.min(score, 15);
    else if (salaryOk === false) score = Math.max(0, score - 25);
    if (interviewRisk === "HIGH") score = Math.max(0, score - 20);
    else if (interviewRisk === "MEDIUM") score = Math.max(0, score - 5);
    if (!noticeCompat) score = Math.max(0, score - 12);
    if (edWarn && edWarn.includes("requirement")) score = Math.max(0, score - 15);
    else if (edWarn) score = Math.max(0, score - 5);

    const aHits = (cfg.tracks.track_a.boost_keywords || []).filter(k => termPresent(k, lowered)).length;
    const bHits = (cfg.tracks.track_b.boost_keywords || []).filter(k => termPresent(k, lowered)).length;
    const recResume = (aHits > bHits || locBucket === "Remote-Global")
      ? cfg.tracks.track_a.label
      : cfg.tracks.track_b.label;

    const proofs = (cfg.proof_point_library || [])
      .map(item => ({ hits: item.triggers.filter(t => termPresent(t, lowered)).length, story: item.story }))
      .filter(x => x.hits >= 1)
      .sort((a, b) => b.hits - a.hits)
      .slice(0, 3)
      .map(x => x.story);

    const topProof = proofs[0] || "automated workflows saving 500+ hrs/month (Leonidas Award) and cut launch SLAs by 50%.";
    const pitch = `Hi Hiring Team at ${company} — I am reaching out regarding the ${title} opening. With 4+ years across e-commerce and advertising operations (Ergode IT Services & TTEC/Rakuten), my strength is turning operational bottlenecks into measurable efficiency. Highlight: ${topProof} (60-day notice, open to discussion).`;

    return {
      job_id: `eval_${Date.now()}`,
      source: raw.source || "manual",
      title,
      company,
      location: location || (locBucket.startsWith("Remote") ? "Remote" : "India"),
      work_mode: locBucket.startsWith("Remote") ? "Remote" : workMode,
      salary_text: salaryText || null,
      salary_ok: salaryOk,
      url: raw.url || "",
      description: desc,
      fit_score: Number(Math.min(100, Math.max(0, score)).toFixed(1)),
      fit_breakdown: {
        operations_process: opsPts,
        ai_workflow_automation: aiPts,
        domain_ecommerce_adtech: domPts,
        logistics_location_notice: logPts
      },
      interview_risk: interviewRisk,
      risk_triggers: triggers,
      location_bucket: locBucket,
      notice_compatible: noticeCompat,
      notice_warning: noticeWarn,
      education_warning: edWarn,
      recommended_resume: recResume,
      matched_proof_points: proofs,
      rejected_reason: rejectedReason,
      tailored_pitch: pitch,
      status: "new"
    };
  }

  function applyStatusLocal(jobId, status) {
    state.localStatuses[jobId] = status;
    safeSetStorage("job_radar_statuses", state.localStatuses);
    const job = state.jobs.find(j => j.job_id === jobId);
    if (job) job.status = status;

    if (!state.offlineMode) {
      fetch("/api/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId, status })
      }).catch(() => {});
    }
    renderAll();
    if (state.selectedId === jobId) {
      renderDetail(job);
    }
    showToast(`Marked as ${status}`);
  }

  function filteredJobs() {
    const q = document.getElementById("searchInput").value.trim().toLowerCase();
    const src = document.getElementById("filterSource").value;
    const loc = document.getElementById("filterLocation").value;
    const risk = document.getElementById("filterRisk").value;
    const track = document.getElementById("filterTrack").value;
    const status = document.getElementById("filterStatus").value;

    return state.jobs.filter(j => {
      if (q) {
        const hay = `${j.title} ${j.company} ${j.location} ${(j.skills_listed || []).join(" ")} ${j.description}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (src !== "all" && j.source !== src) return false;
      if (loc !== "all" && j.location_bucket !== loc) return false;
      if (risk === "safe" && (j.interview_risk !== "LOW" || j.rejected_reason)) return false;
      if (risk === "low_med" && (j.interview_risk === "HIGH" || j.rejected_reason)) return false;
      if (track !== "all" && !j.recommended_resume.includes(track)) return false;
      if (status === "active" && j.status === "skip") return false;
      if (!["all", "active"].includes(status) && j.status !== status) return false;
      return true;
    });
  }

  function renderKpis() {
    const nonRejected = state.jobs.filter(j => !j.rejected_reason);
    const safeFit = nonRejected.filter(j => j.interview_risk === "LOW" && j.fit_score >= 65);
    const remote = nonRejected.filter(j => j.location_bucket !== "India-Onsite/Hybrid");
    const pipeline = nonRejected.filter(j => ["shortlisted", "applied", "interviewing"].includes(j.status));

    document.getElementById("kpiTotal").textContent = nonRejected.length;
    document.getElementById("kpiSafeFit").textContent = safeFit.length;
    document.getElementById("kpiRemote").textContent = remote.length;
    document.getElementById("kpiPipeline").textContent = pipeline.length;
  }

  function riskPill(risk, rejected) {
    if (rejected) return `<span class="pill pill-rose">Rejected: ${escapeHtml(rejected)}</span>`;
    if (risk === "LOW") return `<span class="pill pill-emerald">Interview Safe (LOW Risk)</span>`;
    if (risk === "MEDIUM") return `<span class="pill pill-amber">Verify Risk (MEDIUM)</span>`;
    return `<span class="pill pill-rose">Coding/BA Trap (HIGH Risk)</span>`;
  }

  function renderJobList() {
    const listEl = document.getElementById("jobList");
    const items = filteredJobs();
    if (!items.length) {
      listEl.innerHTML = `<div class="card"><p class="muted">No listings match the current filters. Try switching Risk filter to "Low + Medium Risk" or clearing search text.</p></div>`;
      return;
    }

    listEl.innerHTML = items.map(j => {
      const scoreClass = j.fit_score >= 70 ? "score-high" : (j.fit_score >= 45 ? "score-mid" : "score-low");
      const selected = j.job_id === state.selectedId ? "selected" : "";
      const expText = (j.exp_min != null) ? `${j.exp_min}–${j.exp_max} yrs` : "Exp flexible";
      const trackBadge = j.recommended_resume.includes("Track A") ? "Track A: AI Ops" : "Track B: Ops Excellence";
      const salaryBadge = j.salary_text
        ? `<span class="pill ${j.salary_ok === false ? "pill-rose" : "pill-emerald"}">${escapeHtml(j.salary_text)}</span>`
        : "";
      const noticeBadge = j.notice_compatible === false
        ? `<span class="pill pill-rose">Immediate Joiner Conflict</span>`
        : `<span class="pill">60d Notice OK</span>`;

      return `
        <article class="job-card ${selected}" data-job-id="${escapeHtml(j.job_id)}">
          <div class="job-card-top">
            <div>
              <h3 class="job-title">${escapeHtml(j.title)}</h3>
              <p class="job-company">${escapeHtml(j.company)} &bull; ${escapeHtml(j.location)}</p>
            </div>
            <div class="score-ring ${scoreClass}">${Math.round(j.fit_score)}%</div>
          </div>
          <div class="badge-row">
            <span class="pill pill-indigo">${escapeHtml(j.source.toUpperCase())}</span>
            <span class="pill">${escapeHtml(j.location_bucket)}</span>
            ${riskPill(j.interview_risk, j.rejected_reason)}
            ${salaryBadge}
            ${noticeBadge}
            ${j.education_warning ? `<span class="pill pill-amber">Degree Gate</span>` : ""}
            <span class="pill">${escapeHtml(trackBadge)}</span>
          </div>
          <div class="job-meta">
            <span>${escapeHtml(expText)}</span>
            ${j.posted_text ? `<span>Posted: ${escapeHtml(j.posted_text)}</span>` : ""}
            <span>Status: <strong>${escapeHtml(j.status.toUpperCase())}</strong></span>
          </div>
          <div class="card-quick-actions">
            ${j.url ? `<a class="btn btn-primary btn-sm" href="${escapeHtml(j.url)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">Apply &rarr;</a>` : ""}
            <button class="btn btn-outline btn-sm" type="button" data-action="shortlisted" data-id="${escapeHtml(j.job_id)}">Shortlist</button>
            <button class="btn btn-ghost btn-sm" type="button" data-action="applied" data-id="${escapeHtml(j.job_id)}">Applied</button>
            <button class="btn btn-ghost btn-sm" type="button" data-action="skip" data-id="${escapeHtml(j.job_id)}">Skip</button>
          </div>
        </article>
      `;
    }).join("");

    listEl.querySelectorAll(".job-card").forEach(card => {
      card.addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-action]");
        if (btn) {
          e.stopPropagation();
          applyStatusLocal(btn.dataset.id, btn.dataset.action);
          return;
        }
        const job = state.jobs.find(x => x.job_id === card.dataset.jobId);
        if (job) openJobInspector(job);
      });
    });
  }

  function buildDetailMarkup(j) {
    const bd = j.fit_breakdown || {};
    const triggersHtml = (j.risk_triggers || []).length
      ? `<ul class="proof-list">${j.risk_triggers.map(t => `<li>${escapeHtml(t)}</li>`).join("")}</ul>`
      : `<p class="muted">No heavy SQL coding, Python software engineering, or formal BABOK traps detected.</p>`;

    const proofsHtml = (j.matched_proof_points || []).length
      ? `<ul class="proof-list">${j.matched_proof_points.map(p => `<li>${escapeHtml(p)}</li>`).join("")}</ul>`
      : `<p class="muted">Highlight Ergode 500+ hrs/mo automation and TTEC 50% SLA improvement.</p>`;

    return `
      <div>
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;">
          <div>
            <h3 style="margin:0;">${escapeHtml(j.title)}</h3>
            <p class="job-company">${escapeHtml(j.company)} &bull; ${escapeHtml(j.location)}</p>
          </div>
          <span class="score-ring ${j.fit_score >= 70 ? "score-high" : "score-mid"}">${Math.round(j.fit_score)}%</span>
        </div>
          <div class="badge-row" style="margin-top:10px;">
          ${riskPill(j.interview_risk, j.rejected_reason)}
          <span class="pill pill-indigo">Use: ${escapeHtml(j.recommended_resume)}</span>
          ${j.notice_warning ? `<span class="pill pill-rose">${escapeHtml(j.notice_warning)}</span>` : ""}
          ${j.education_warning ? `<span class="pill pill-amber">${escapeHtml(j.education_warning)}</span>` : ""}
        </div>

        <div class="detail-section">
          <h4>Score Breakdown</h4>
          <div class="breakdown-grid">
            <div class="breakdown-item"><strong>Ops &amp; Process:</strong> ${bd.operations_process || 0} / 35</div>
            <div class="breakdown-item"><strong>AI &amp; Workflows:</strong> ${bd.ai_workflow_automation || 0} / 25</div>
            <div class="breakdown-item"><strong>E-Comm / AdTech:</strong> ${bd.domain_ecommerce_adtech || 0} / 20</div>
            <div class="breakdown-item"><strong>Location &amp; Notice:</strong> ${bd.logistics_location_notice || 0} / 25</div>
          </div>
        </div>

        <div class="detail-section">
          <h4>Interview-Safety Check</h4>
          ${triggersHtml}
        </div>

        <div class="detail-section">
          <h4>Proof Points to Lead With (From Your Resume)</h4>
          ${proofsHtml}
        </div>

        <div class="detail-section">
          <h4>Tailored Outreach Pitch</h4>
          <div class="pitch-box">${escapeHtml(j.tailored_pitch)}</div>
          <div class="btn-group" style="margin-top:8px;">
            <button class="btn btn-primary btn-sm" type="button" data-copy-pitch>Copy Pitch</button>
            ${j.url ? `<a class="btn btn-emerald btn-sm" href="${escapeHtml(j.url)}" target="_blank" rel="noopener">Open Original Posting &rarr;</a>` : ""}
          </div>
        </div>

        <div class="detail-section">
          <h4>Full Extracted Summary</h4>
          <p class="muted" style="white-space:pre-line;">${escapeHtml(j.description)}</p>
        </div>
      </div>
    `;
  }

  function wireCopyPitch(container, pitchText) {
    const btn = container.querySelector("[data-copy-pitch]");
    if (btn) {
      btn.addEventListener("click", () => {
        navigator.clipboard?.writeText(pitchText).then(() => showToast("Pitch copied!"));
      });
    }
  }

  function renderDetail(j) {
    const pane = document.getElementById("detailPane");
    if (!j) return;
    pane.innerHTML = buildDetailMarkup(j);
    wireCopyPitch(pane, j.tailored_pitch);
  }

  function openJobInspector(j) {
    state.selectedId = j.job_id;
    renderJobList();
    renderDetail(j);
    if (window.innerWidth < 960) {
      const sheetBody = document.getElementById("mobileSheetBody");
      sheetBody.innerHTML = buildDetailMarkup(j);
      wireCopyPitch(sheetBody, j.tailored_pitch);
      document.getElementById("mobileSheetBackdrop").hidden = false;
    }
  }

  function renderProfileSnippets() {
    const root = document.getElementById("profileSnippets");
    root.innerHTML = PROFILE_SNIPPETS.map((s, idx) => `
      <div class="snippet-card">
        <div class="snippet-head">
          <strong>${escapeHtml(s.title)}</strong>
          <button class="btn btn-outline btn-sm" type="button" data-snippet-idx="${idx}">Copy</button>
        </div>
        <pre class="snippet-text">${escapeHtml(s.body)}</pre>
      </div>
    `).join("");

    root.querySelectorAll("button[data-snippet-idx]").forEach(btn => {
      btn.addEventListener("click", () => {
        const txt = PROFILE_SNIPPETS[Number(btn.dataset.snippetIdx)].body;
        navigator.clipboard?.writeText(txt).then(() => showToast("Copied to clipboard!"));
      });
    });
  }

  function renderAll() {
    renderKpis();
    renderJobList();
  }

  function downloadCsvClient() {
    const headers = ["Title", "Company", "Source", "Location", "Bucket", "Fit Score", "Interview Risk", "Resume Track", "Salary", "Status", "URL"];
    const rows = state.jobs.map(j => [
      j.title, j.company, j.source, j.location, j.location_bucket, j.fit_score,
      j.interview_risk, j.recommended_resume, j.salary_text || "", j.status, j.url
    ]);
    const csvContent = [headers, ...rows]
      .map(r => r.map(v => `"${String(v ?? "").replaceAll('"', '""')}"`).join(","))
      .join("\r\n");
    const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "abhishek_job_radar.csv";
    a.click();
  }

  function inferGitHubRepoSlug() {
    const saved = safeGetStorage("job_radar_gh_repo", "");
    if (saved) return saved;
    const host = window.location.hostname || "";
    if (host.endsWith(".github.io")) {
      const owner = host.split(".")[0];
      const parts = window.location.pathname.split("/").filter(Boolean);
      const repo = parts[0] || `${owner}.github.io`;
      return `${owner}/${repo}`;
    }
    return "";
  }

  function applyLoadedPayload(data, isStaticSite) {
    state.config = data.config;
    state.jobs = (data.jobs || []).map(j => ({
      ...j,
      status: isStaticSite ? (state.localStatuses[j.job_id] || j.status || "new") : (j.status || "new")
    }));
    const meta = data.meta || {};
    const metaEl = document.getElementById("refreshMetaText");
    if (metaEl) {
      if (meta.last_refreshed_ist) {
        metaEl.textContent = `Last updated: ${meta.last_refreshed_ist} (${meta.total_jobs || state.jobs.length} roles)`;
      } else {
        metaEl.textContent = `Loaded ${state.jobs.length} curated roles. Push to GitHub Pages for daily 8 AM IST auto-refresh.`;
      }
    }
  }

  function setPrivatePdfNotice(msg) {
    const pdfBox = document.getElementById("pdfDownloadGroup");
    if (pdfBox) {
      pdfBox.innerHTML = `<p class="muted" style="margin:0;">${msg}</p>`;
    }
  }

  async function pullLatestFeed() {
    if (window.location.protocol === "file:" || window.location.protocol === "content:") {
      showToast("Offline file mode — open your GitHub Pages app URL to pull live updates");
      return;
    }
    try {
      const pwaRes = await fetch(`./data/jobs_payload.json?t=${Date.now()}`, { cache: "no-store" });
      if (pwaRes.ok) {
        applyLoadedPayload(await pwaRes.json(), true);
        renderAll();
        showToast("Pulled latest Cloud PWA feed!");
        return;
      }
    } catch {
      // Fallback to local server
    }
    try {
      const apiRes = await fetch(`./api/jobs?t=${Date.now()}`, { cache: "no-store" });
      if (apiRes.ok) {
        applyLoadedPayload(await apiRes.json(), false);
        renderAll();
        showToast("Reloaded local server feed!");
      }
    } catch {
      showToast("Could not reach update feed");
    }
  }

  async function init() {
    state.localStatuses = safeGetStorage("job_radar_statuses", {});
    renderProfileSnippets();

    const ghInput = document.getElementById("ghRepoInput");
    if (ghInput) {
      ghInput.value = inferGitHubRepoSlug();
      ghInput.addEventListener("change", () => {
        safeSetStorage("job_radar_gh_repo", ghInput.value.trim().replace(/^https?:\/\/github\.com\//i, "").replace(/\/+$/, ""));
        showToast("GitHub repo saved!");
      });
    }

    const embeddedEl = document.getElementById("embedded-data");
    let embedded = null;
    try {
      embedded = JSON.parse(embeddedEl.textContent || "null");
    } catch {
      embedded = null;
    }

    const isFile = window.location.protocol === "file:" || window.location.protocol === "content:";
    let loaded = false;

    if (!isFile) {
      try {
        const pwaRes = await fetch(`./data/jobs_payload.json?t=${Date.now()}`, { cache: "no-store" });
        if (pwaRes.ok) {
          state.offlineMode = true;
          applyLoadedPayload(await pwaRes.json(), true);
          document.getElementById("modeBadge").textContent = "Cloud PWA";
          document.getElementById("lanUrlBox").textContent = window.location.href.split("#")[0];
          setPrivatePdfNotice("Your 2 PDF resumes are stored privately in your Vivo phone's Downloads folder (not uploaded publicly to GitHub Pages).");
          if ("serviceWorker" in navigator) {
            navigator.serviceWorker.register("./sw.js").catch(() => {});
          }
          loaded = true;
        }
      } catch {
        // Not static GitHub Pages host; try local server next
      }
    }

    if (!loaded && !isFile && !(embedded && Array.isArray(embedded.jobs))) {
      try {
        const res = await fetch("./api/jobs");
        if (res.ok) {
          const data = await res.json();
          applyLoadedPayload(data, false);
          const lanUrl = `http://${data.lan_ip}:${window.location.port || 8765}`;
          document.getElementById("lanUrlBox").textContent = lanUrl;
          loaded = true;
        }
      } catch {
        // Fallback to embedded data
      }
    }

    if (!loaded && embedded && Array.isArray(embedded.jobs)) {
      state.offlineMode = true;
      applyLoadedPayload(embedded, true);
      document.getElementById("modeBadge").textContent = "Vivo 5G Offline Mode";
      document.getElementById("lanUrlBox").textContent = "Running standalone offline bundle on device";
      setPrivatePdfNotice("Standalone offline mode: open your saved <strong>Track A</strong> and <strong>Track B</strong> PDFs from your phone's Downloads/Files app.");
    }

    renderAll();
    if (state.jobs.length && window.innerWidth >= 960) {
      state.selectedId = state.jobs[0].job_id;
      renderDetail(state.jobs[0]);
      renderJobList();
    }
  }

  // Event wiring
  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });

  ["searchInput", "filterSource", "filterLocation", "filterRisk", "filterTrack", "filterStatus"].forEach(id => {
    document.getElementById(id).addEventListener("input", renderJobList);
    document.getElementById(id).addEventListener("change", renderJobList);
  });

  document.getElementById("closeSheetBtn").addEventListener("click", () => {
    document.getElementById("mobileSheetBackdrop").hidden = true;
  });
  document.getElementById("mobileSheetBackdrop").addEventListener("click", (e) => {
    if (e.target.id === "mobileSheetBackdrop") {
      document.getElementById("mobileSheetBackdrop").hidden = true;
    }
  });

  document.getElementById("exportCsvBtn").addEventListener("click", () => {
    if (state.offlineMode) downloadCsvClient();
    else window.location.href = "/api/export.csv";
  });
  document.getElementById("syncCsvBtn").addEventListener("click", () => {
    if (state.offlineMode) downloadCsvClient();
    else window.location.href = "/api/export.csv";
  });

  document.getElementById("backupJsonBtn").addEventListener("click", () => {
    const out = {};
    state.jobs.forEach(j => { out[j.job_id] = j.status; });
    const blob = new Blob([JSON.stringify(out, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "job_radar_backup.json";
    a.click();
  });

  document.getElementById("restoreJsonInput").addEventListener("change", async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      Object.entries(parsed).forEach(([id, st]) => applyStatusLocal(id, st));
      showToast("Backup restored!");
    } catch {
      showToast("Invalid backup JSON");
    }
  });

  async function runEvaluate(saveToList) {
    const payload = {
      title: document.getElementById("evalTitle").value,
      company: document.getElementById("evalCompany").value,
      location: document.getElementById("evalLocation").value,
      salary_text: document.getElementById("evalSalary").value,
      description: document.getElementById("evalDesc").value,
      save: saveToList
    };
    let result;
    if (!state.offlineMode) {
      const res = await fetch("/api/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      result = await res.json();
    } else {
      result = evaluateJobClient(payload, state.config);
    }
    if (saveToList) {
      state.jobs.unshift(result);
      renderAll();
      showToast("Evaluated & added to Matches!");
    }
    const container = document.getElementById("evalResult");
    container.innerHTML = `<div class="card">${buildDetailMarkup(result)}</div>`;
    wireCopyPitch(container, result.tailored_pitch);
  }

  document.getElementById("pullLatestBtn")?.addEventListener("click", pullLatestFeed);
  document.getElementById("openGhActionBtn")?.addEventListener("click", () => {
    const slug = (document.getElementById("ghRepoInput")?.value || inferGitHubRepoSlug()).trim();
    if (!slug || !slug.includes("/")) {
      showToast("Enter your repo as username/job-radar first");
      return;
    }
    safeSetStorage("job_radar_gh_repo", slug);
    window.open(`https://github.com/${slug}/actions/workflows/refresh_jobs.yml`, "_blank", "noopener");
  });

  document.getElementById("evalRunBtn").addEventListener("click", () => runEvaluate(false));
  document.getElementById("evalSaveBtn").addEventListener("click", () => runEvaluate(true));
  document.getElementById("evalDemoAcmeBtn").addEventListener("click", () => {
    document.getElementById("evalTitle").value = "Sales Engineer";
    document.getElementById("evalCompany").value = "Acme Corporation";
    document.getElementById("evalLocation").value = "123 Main Street, City, State 12345";
    document.getElementById("evalSalary").value = "";
    document.getElementById("evalDesc").value = "Architect leaf-spine architectures (VxLAN, EVPN), BGP, OSPF, TS/SCI security clearance required, legal right to work in Japan.";
    runEvaluate(false);
  });

  init();
})();
