"""
config.py — Central configuration for the job scraper.
Edit this file to change search queries, locations, or scoring weights.

Profile: Omar Ashour — AI & Data Science graduate, EJUST Alexandria
Targeting: ML, CV, NLP, Data Science, Data Analysis, BI, Research, Teaching
"""

import os

# ── Output paths ──────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE      = os.path.join(BASE_DIR, "job_tracker.xlsx")
SEEN_FILE       = os.path.join(BASE_DIR, "seen_jobs.json")
LOG_FILE        = os.path.join(BASE_DIR, "scraper.log")

# ── Search queries ────────────────────────────────────────────────────────────
# Organised by category — covers every role an AI & Data Science graduate
# could realistically apply for, from core ML to data analysis and teaching.

SEARCH_QUERIES = [

    # ── Core ML / AI ──────────────────────────────────────────────────────────
    "Machine Learning Engineer",
    "Junior Machine Learning Engineer",
    "Machine Learning internship",
    "AI Engineer",
    "Junior AI Engineer",
    "AI internship",
    "Deep Learning Engineer",
    "Deep Learning internship",
    "AI Research Engineer",
    "AI Research internship",
    "MLOps Engineer",
    "MLOps internship",

    # ── Computer Vision ───────────────────────────────────────────────────────
    "Computer Vision Engineer",
    "Computer Vision internship",
    "Image Processing Engineer",
    "Vision AI Engineer",

    # ── NLP / LLM ─────────────────────────────────────────────────────────────
    "NLP Engineer",
    "NLP internship",
    "Natural Language Processing Engineer",
    "LLM Engineer",
    "Conversational AI Engineer",

    # ── Data Science ──────────────────────────────────────────────────────────
    "Data Scientist",
    "Junior Data Scientist",
    "Data Science internship",
    "Applied Data Scientist",

    # ── Data Analysis ─────────────────────────────────────────────────────────
    "Data Analyst",
    "Junior Data Analyst",
    "Data Analyst internship",
    "Business Intelligence Analyst",
    "BI Analyst",
    "Analytics Engineer",
    "Analytics internship",
    "Reporting Analyst",

    # ── Data Engineering ──────────────────────────────────────────────────────
    "Data Engineer",
    "Junior Data Engineer",
    "Data Engineering internship",

    # ── Python / Software (AI-adjacent) ───────────────────────────────────────
    "Python Developer",
    "Python Developer AI",
    "Python Developer Data",
    "Python internship",
    "Backend Developer Python",
    "Software Engineer Python AI",

    # ── Research / Academic ───────────────────────────────────────────────────
    "Research Assistant AI",
    "Research Assistant Data Science",
    "AI Research Assistant",

    # ── Teaching / Instruction ────────────────────────────────────────────────
    "AI Instructor",
    "Data Science Instructor",
    "Machine Learning Instructor",
    "AI Trainer",
    "Python Instructor",

]

# ── Egypt-specific locations for Wuzzuf / Bayt ───────────────────────────────
EGYPT_LOCATIONS = ["Cairo", "Alexandria", "Egypt", "Remote"]

# ── Work type keywords ────────────────────────────────────────────────────────
REMOTE_KEYWORDS = ["remote", "work from home", "wfh", "fully remote"]
HYBRID_KEYWORDS = ["hybrid"]
ONSITE_KEYWORDS = ["on-site", "onsite", "in-office", "cairo", "alexandria"]

# ── Skills scoring ────────────────────────────────────────────────────────────
# Weight reflects how directly the keyword maps to your actual skill set.
# High weight (3): your core strengths — mention these in your CV
# Medium weight (2): solid skills or strong role signals
# Low weight (1): supporting skills, worth noting but not defining

SKILL_KEYWORDS_POSITIVE = {

    # ── Core ML / DL — your main stack ───────────────────────────────────────
    "pytorch":              3,
    "pytorch geometric":    3,
    "tensorflow":           2,
    "keras":                2,
    "deep learning":        3,
    "neural network":       2,
    "gnn":                  3,
    "graph neural":         3,
    "gatv2":                3,
    "gineconv":             3,
    "transformer":          2,
    "attention mechanism":  2,
    "bert":                 2,
    "sentence-bert":        2,
    "hugging face":         2,
    "llm":                  2,
    "large language model": 2,
    "rag":                  2,
    "hnsw":                 2,
    "vector database":      1,
    "embedding":            1,

    # ── Computer Vision — your graduation project ─────────────────────────────
    "computer vision":      3,
    "opencv":               2,
    "yolo":                 2,
    "yolov8":               3,
    "object detection":     2,
    "image segmentation":   2,
    "action recognition":   3,
    "pose estimation":      2,
    "mediapipe":            2,
    "image classification": 2,
    "video analysis":       2,
    "scene understanding":  2,

    # ── NLP ───────────────────────────────────────────────────────────────────
    "nlp":                  2,
    "natural language":     2,
    "text classification":  2,
    "sentiment analysis":   2,
    "named entity":         2,
    "information retrieval": 1,

    # ── Data Science ──────────────────────────────────────────────────────────
    "data science":         2,
    "scikit-learn":         2,
    "sklearn":              2,
    "statistical analysis": 2,
    "predictive modeling":  2,
    "feature engineering":  2,
    "model evaluation":     1,
    "a/b testing":          1,
    "hypothesis testing":   1,
    "regression":           1,
    "classification":       1,
    "clustering":           1,

    # ── Data Analysis / BI ────────────────────────────────────────────────────
    "data analysis":        2,
    "data analytics":       2,
    "business intelligence": 2,
    "power bi":             2,
    "tableau":              2,
    "looker":               1,
    "dashboarding":         1,
    "reporting":            1,
    "kpi":                  1,
    "data visualization":   2,
    "matplotlib":           1,
    "seaborn":              1,
    "plotly":               1,

    # ── Data Engineering ──────────────────────────────────────────────────────
    "data engineering":     1,
    "etl":                  1,
    "pipeline":             1,
    "spark":                1,
    "airflow":              1,
    "kafka":                1,
    "dbt":                  1,

    # ── Python / Dev tools ────────────────────────────────────────────────────
    "python":               1,
    "pandas":               1,
    "numpy":                1,
    "jupyter":              1,
    "mlflow":               1,
    "docker":               1,
    "git":                  1,
    "fastapi":              1,
    "flask":                1,
    "django":               1,

    # ── Databases ─────────────────────────────────────────────────────────────
    "sql":                  1,
    "postgresql":           1,
    "mysql":                1,
    "mongodb":              1,

    # ── Cloud / MLOps ─────────────────────────────────────────────────────────
    "aws":                  1,
    "gcp":                  1,
    "azure":                1,
    "mlops":                2,
    "model deployment":     1,
    "model serving":        1,

    # ── Research / Teaching ───────────────────────────────────────────────────
    "research":             1,
    "academic":             1,
    "teaching":             1,
    "instructor":           1,
    "curriculum":           1,
    "workshop":             1,
    "ieee":                 1,

    # ── Junior / intern signals ───────────────────────────────────────────────
    "junior":               2,
    "fresh graduate":       2,
    "entry level":          2,
    "intern":               2,
    "internship":           2,
    "0-2 years":            2,
    "0-1 year":             2,
    "recent graduate":      2,
    "new graduate":         2,
    "graduate":             1,

    # ── Domain bonus ─────────────────────────────────────────────────────────
    "surveillance":         1,
    "safety":               1,
    "healthcare":           1,
    "medical imaging":      2,
    "robotics":             1,
    "autonomous":           1,
    "fintech":              1,
    "edtech":               1,

    # ── Role title keywords — for card-level scraping (Wuzzuf/Bayt) ──────────
    # These platforms return only title+company+location at card level with no
    # full JD text, so role keywords must score from the title alone.
    "data analyst":         2,
    "data analysis":        2,
    "data scientist":       2,
    "data science":         2,
    "data engineer":        2,
    "machine learning":     2,
    "ai engineer":          2,
    "ai research":          2,
    "nlp engineer":         2,
    "research assistant":   2,
    "bi analyst":           2,
    "analytics engineer":   2,
    "reporting analyst":    2,
    "ml engineer":          2,
    "llm engineer":         2,
    "vision engineer":      2,
    "python developer":     2,
}

SKILL_KEYWORDS_NEGATIVE = {
    "10+ years":            -5,
    "8+ years":             -5,
    "7+ years":             -4,
    "5+ years":             -3,
    "senior":               -3,
    "lead":                 -2,
    "manager":              -3,
    "director":             -4,
    "vp of":                -5,
    "head of":              -4,
    "chief":                -5,
    "data entry":           -5,
    "excel only":           -4,
    "no coding":            -5,
    "non-technical":        -4,
}

# ── Remote API two-layer relevance filter ─────────────────────────────────────
# Applied to RemoteOK, WWR, Himalayas, Jobicy only.
# These platforms return every remote job regardless of category.

REMOTE_TITLE_BLOCKLIST = [
    "account executive", "account manager",
    "sales", "marketing", "advertising",
    "seo", "sem", "copywriter", "content writer",
    "recruiter", "hr ", "human resource",
    "customer success", "customer support", "customer service",
    "business development",
    "product manager", "project manager",
    "finance", "accounting", "bookkeeper",
    "legal", "paralegal", "operations manager",
    "social media", "graphic design", "ux design",
    "office manager", "executive assistant",
    "network engineer", "devops", "sysadmin",
    "cybersecurity", "penetration tester",
]

REMOTE_CORE_TITLE_KEYWORDS = [
    # ML / AI
    "machine learning", "ml engineer", "ml intern", " ml ",
    "deep learning", "neural", "ai engineer", "ai research",
    "artificial intelligence", "llm", "large language",
    # Vision / NLP
    "computer vision", "nlp", "natural language", "opencv", "yolo",
    "cv engineer",
    # Data roles — all now included
    "data scien", "data analyst", "data engineer", "data science",
    "analytics engineer", "analytics intern", "bi analyst",
    "business intelligence",
    # Frameworks
    "pytorch", "tensorflow",
    # Research / Teaching
    "research engineer", "research assistant",
    "ai instructor", "data instructor", "ml instructor",
    "ai trainer", "python instructor",
    # MLOps
    "mlops",
    # Catch-all for internships
    "intern",
]

# ── Minimum match score to include in Excel ───────────────────────────────────
MIN_SCORE = 2

# ── Scraping behaviour ────────────────────────────────────────────────────────
REQUEST_DELAY_SEC     = 2.5
PLAYWRIGHT_TIMEOUT    = 20000
MAX_RESULTS_PER_QUERY = 15
MAX_JOB_AGE_DAYS      = 30   # skip jobs older than this (0 = no filter)

# ── Notification ─────────────────────────────────────────────────────────────
NOTIFICATION_TITLE   = "Job Scraper — Run Complete"
NOTIFICATION_TIMEOUT = 12
