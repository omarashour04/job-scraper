"""
config.py — Central configuration for the job scraper.
Edit this file to change search queries, locations, or scoring weights.
"""

import os

# ── Output paths ──────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE      = os.path.join(BASE_DIR, "job_tracker.xlsx")
SEEN_FILE       = os.path.join(BASE_DIR, "seen_jobs.json")
LOG_FILE        = os.path.join(BASE_DIR, "scraper.log")

# ── Search queries ────────────────────────────────────────────────────────────
SEARCH_QUERIES = [
    "Machine Learning Engineer",
    "Computer Vision Engineer",
    "Junior AI Engineer",
    "Data Scientist",
    "Deep Learning Engineer",
    "NLP Engineer",
    "AI Research Engineer",
    "MLOps Engineer",
    "Python Developer AI",
    "ML internship",
    "AI internship",
    "Data Science internship",
    "Computer Vision internship",
]

# ── Egypt-specific locations for Wuzzuf / Bayt ───────────────────────────────
EGYPT_LOCATIONS = ["Cairo", "Alexandria", "Egypt", "Remote"]

# ── Work type keywords (used in scoring and filtering) ───────────────────────
REMOTE_KEYWORDS   = ["remote", "work from home", "wfh", "fully remote"]
HYBRID_KEYWORDS   = ["hybrid"]
ONSITE_KEYWORDS   = ["on-site", "onsite", "in-office", "cairo", "alexandria"]

# ── Skills scoring: presence in JD description raises match score ─────────────
SKILL_KEYWORDS_POSITIVE = {
    # Core ML/DL — high weight
    "pytorch":          3,
    "tensorflow":       2,
    "deep learning":    3,
    "neural network":   2,
    "computer vision":  3,
    "gnn":              3,
    "graph neural":     3,
    "transformer":      2,
    "bert":             2,
    "nlp":              2,
    "yolo":             2,
    "opencv":           2,
    "object detection": 2,
    "image segmentation": 2,
    # Python / MLOps
    "python":           1,
    "scikit-learn":     1,
    "mlflow":           1,
    "docker":           1,
    # Data Engineering
    "sql":              1,
    "postgresql":       1,
    "django":           1,
    # Internship / junior friendly
    "junior":           2,
    "fresh graduate":   2,
    "entry level":      2,
    "intern":           2,
    "0-2 years":        2,
    "0-1 year":         2,
    "recent graduate":  2,
    # Domain bonus
    "surveillance":     1,
    "healthcare":       1,
    "robotics":         1,
    "autonomous":       1,
}

SKILL_KEYWORDS_NEGATIVE = {
    "10+ years":        -5,
    "8+ years":         -5,
    "senior":           -3,
    "lead":             -2,
    "manager":          -3,
    "director":         -4,
    "data entry":       -5,
    "excel only":       -4,
    "bi analyst":       -3,
    "tableau only":     -3,
}

# ── Minimum match score to include in Excel ───────────────────────────────────
MIN_SCORE = 3

# ── Scraping behaviour ────────────────────────────────────────────────────────
REQUEST_DELAY_SEC   = 2.5   # polite delay between HTTP requests
PLAYWRIGHT_TIMEOUT  = 20000 # ms — page load timeout for browser-based scrapers
MAX_RESULTS_PER_QUERY = 15  # max listings to pull per query per platform

# ── Notification ─────────────────────────────────────────────────────────────
NOTIFICATION_TITLE   = "Job Scraper — Run Complete"
NOTIFICATION_TIMEOUT = 12  # seconds the toast stays visible
