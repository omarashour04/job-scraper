# Job Scraper — Automated AI/ML Job Search

A fully automated job scraper that searches **LinkedIn**, **Wuzzuf**, **Bayt**, **RemoteOK**, **We Work Remotely**, **Himalayas**, and **Jobicy** for AI/ML/Data Science roles and internships, scores each listing against a skills profile, deduplicates across runs, and writes results to a formatted Excel tracker — then sends a Windows desktop notification when done.

Designed for fresh graduates and junior candidates targeting roles in Egypt (Cairo/Alexandria, hybrid/onsite) and remote positions abroad.

---

## Features

- Searches 7 job platforms in a single run
- Covers hybrid, onsite (Egypt), remote (Egypt), and remote (worldwide)
- Relevance scoring engine — filters out senior-only and irrelevant listings automatically
- Persistent deduplication across runs — never writes the same job twice
- Color-coded Excel output with clickable URLs and a live dashboard sheet
- Silent Windows background task — fires once per day when you open your laptop, hard-killed after 20 minutes

---

## Platforms Covered

| Platform | Region | Method |
|---|---|---|
| LinkedIn | Egypt + Remote worldwide | Public guest search API |
| Wuzzuf | Egypt | HTML scraping |
| Bayt | Egypt | HTML scraping |
| RemoteOK | Worldwide remote | JSON API |
| We Work Remotely | Worldwide remote | RSS feed |
| Himalayas | Worldwide remote | JSON API |
| Jobicy | Worldwide remote | JSON API |

---

## Output — job_tracker.xlsx

Each run appends new qualifying listings to the tracker. Rows are color-coded by priority:

- **Green** — High priority (score ≥ 8)
- **Yellow** — Medium priority (score 5–7)
- **White** — Low priority (score 3–4)

Columns: `Date Found`, `Date Posted`, `Title`, `Company`, `Source`, `Work Type`, `Location`, `Match Score`, `Priority`, `Key Skills`, `URL` (hyperlinked), `Status`, `Query`, `Notes`

The `Status` column is yours to maintain: `Not Applied` → `Applied` → `Rejected` / `Offer`.

A `Dashboard` sheet tracks totals by priority and source platform using live Excel formulas.

---

## Project Structure

```
job_scraper/
├── main.py                     # Orchestrator — run this
├── config.py                   # All settings: queries, keywords, scoring weights
├── scorer.py                   # Relevance scoring and keyword extraction
├── deduplicator.py             # Persistent cross-run URL deduplication
├── excel_writer.py             # Creates and appends to job_tracker.xlsx
├── notifier.py                 # Windows desktop notification (win10toast / plyer)
├── scrapers/
│   ├── linkedin.py             # LinkedIn public guest API
│   ├── wuzzuf.py               # Wuzzuf.net HTML scraper
│   ├── bayt.py                 # Bayt.com HTML scraper
│   └── remote_abroad.py       # RemoteOK, WWR, Himalayas, Jobicy
├── install_startup_task.ps1    # Windows Task Scheduler setup (run once)
├── job_scraper_startup.bat     # Alternative: simple Startup folder method
├── requirements.txt
└── .gitignore
```

---

## Setup

### Prerequisites

- Python 3.10 or higher
- Windows 10 / 11 (for the startup task and toast notifications)
- Git

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/job-scraper.git
cd job-scraper
```

### 2. Create a virtual environment

```cmd
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```cmd
pip install -r requirements.txt
pip install win10toast
```

### 4. Run manually to verify

```cmd
python main.py --quick
```

You should see log output in the terminal, a `job_tracker.xlsx` file appear in the folder, and a desktop notification.

---

## Startup Task Installation

This registers a Windows Task Scheduler task that runs the scraper automatically once per day, triggered by login or screen unlock.

Open PowerShell as Administrator:

```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
.\install_startup_task.ps1
```

**Behaviour after installation:**
- Fires on every login, screen unlock, or lid open
- Checks a stamp file — if the scraper already ran today it exits immediately (so unlocking mid-day does not re-trigger it)
- Waits 30 seconds after wakeup for the network to connect before scraping
- Hard-killed after 20 minutes regardless of state
- Runs at below-normal CPU priority — will not compete with your active work
- No window or terminal flash — completely silent

**Useful commands:**

Force a re-run today (delete the stamp):
```powershell
Remove-Item "$env:USERPROFILE\Desktop\job-scraper\.last_run_date"
```

Uninstall the task:
```powershell
Unregister-ScheduledTask -TaskName "JobScraper_Ashour" -Confirm:$false
```

---

## CLI Usage

```
python main.py                          # Full run — all platforms
python main.py --quick                  # Skip LinkedIn (faster, avoids rate-limiting)
python main.py --platform wuzzuf        # Single platform
python main.py --platform bayt
python main.py --platform linkedin
python main.py --platform "remote abroad"
```

---

## Configuration

All settings are in `config.py`. Key options:

| Setting | Description |
|---|---|
| `SEARCH_QUERIES` | List of job titles to search for |
| `SKILL_KEYWORDS_POSITIVE` | Skills that increase the match score, with weights |
| `SKILL_KEYWORDS_NEGATIVE` | Signals that decrease the score (e.g. "10+ years", "data entry") |
| `MIN_SCORE` | Minimum score to include in Excel (default: 3) |
| `MAX_RESULTS_PER_QUERY` | Max listings to pull per query per platform (default: 15) |
| `REQUEST_DELAY_SEC` | Polite delay between HTTP requests (default: 2.5s) |

To add a new job title to search:
```python
SEARCH_QUERIES = [
    ...
    "Computer Vision Intern",
]
```

To increase the weight of a skill:
```python
SKILL_KEYWORDS_POSITIVE = {
    ...
    "pytorch geometric": 4,
}
```

---

## How Scoring Works

Each listing is scored by scanning the title, company, location, and description for keyword matches:

- Keyword matches in `SKILL_KEYWORDS_POSITIVE` add their configured weight to the score
- Keyword matches in `SKILL_KEYWORDS_NEGATIVE` subtract from the score
- Remote location adds +2, hybrid adds +1, Egypt location adds +1
- Score is floored at 0

Priority labels: **High** (≥ 8), **Medium** (5–7), **Low** (3–4), **Skip** (< 3, not written to Excel)

---

## Notes on LinkedIn

LinkedIn is the most aggressive platform for bot detection. The scraper uses their public guest job search API (no login required for card-level data), but rate limiting is possible. `--quick` mode skips LinkedIn entirely and is the default for the daily automated run. Run the full scrape manually when you want LinkedIn results included.

---

## License

MIT License. See `LICENSE` for details.
