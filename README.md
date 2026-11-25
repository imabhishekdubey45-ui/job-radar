# Job Radar — Operations & AI Workflow Workbench

Mobile-first job radar, interview-safety evaluator, and daily GitHub Actions auto-refresh PWA.

## Daily Phone Workflow (GitHub Pages + GitHub Mobile App)

1. **Auto-Refresh (Daily 8:00 AM IST)**: `.github/workflows/refresh_jobs.yml` fetches live global remote & visa-sponsored operations roles (`Himalayas`, `Arbeitnow`, `Jobicy`), merges them with curated India/Startup listings (`data/jobs_seed.json`), evaluates interview safety (`LOW`/`MEDIUM`/`HIGH`), rebuilds `docs/` and `dist/job_radar_mobile.html`, and deploys to GitHub Pages.
2. **Manual Refresh Anytime From Phone**: Open the **GitHub Android App** → **Actions** → **Refresh Jobs & Deploy Mobile PWA** → **Run workflow** (or tap **Open GitHub Refresh** inside the app's **Phone & PDFs** tab).
3. **Install on Vivo 5G Home Screen**: Open your GitHub Pages URL (`https://<your-username>.github.io/<repo-name>/`) in Chrome on Android and tap **Install App** / **Add to Home Screen**.

## Privacy Notes
- Personal PDF resumes (`resumes/output/*.pdf`, `ready_for_phone/`), contact numbers, and local tracker files are excluded via `.gitignore` and never published to GitHub Pages.

## Local Tests & Development
```powershell
python -m unittest discover -s tests -v
python server.py --host 0.0.0.0 --port 8765
```
