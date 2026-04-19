"""
scorer.py — Computes a relevance match score for a job listing.

Score is built from:
  1. Skill keyword matches in title + description
  2. Work-type alignment (remote / hybrid / onsite)
  3. Experience-level signals (junior, intern, 0-2 years)
  4. Negative signals (senior-only, BI-only, data entry, etc.)
"""

import re
from config import (
    SKILL_KEYWORDS_POSITIVE,
    SKILL_KEYWORDS_NEGATIVE,
    REMOTE_KEYWORDS,
    HYBRID_KEYWORDS,
    MIN_SCORE,
)


def _text(job: dict) -> str:
    """Concatenate all searchable text fields into one lower-cased blob."""
    return " ".join([
        job.get("title", ""),
        job.get("company", ""),
        job.get("location", ""),
        job.get("description", ""),
        job.get("work_type", ""),
    ]).lower()


def score_job(job: dict) -> int:
    """
    Returns an integer match score for the given job dict.

    Job dict expected keys:
        title, company, location, description, work_type, source
    """
    blob = _text(job)
    score = 0

    # ── Positive keyword matching ─────────────────────────────────────────────
    for kw, weight in SKILL_KEYWORDS_POSITIVE.items():
        if re.search(r'\b' + re.escape(kw) + r'\b', blob):
            score += weight

    # ── Negative keyword matching ─────────────────────────────────────────────
    for kw, penalty in SKILL_KEYWORDS_NEGATIVE.items():
        if re.search(r'\b' + re.escape(kw) + r'\b', blob):
            score += penalty  # penalty is already negative

    # ── Remote / abroad bonus ─────────────────────────────────────────────────
    if any(kw in blob for kw in REMOTE_KEYWORDS):
        score += 2

    if any(kw in blob for kw in HYBRID_KEYWORDS):
        score += 1

    # ── Egypt-specific bonus (we want local + remote) ─────────────────────────
    if any(loc in blob for loc in ["cairo", "alexandria", "egypt"]):
        score += 1

    return max(score, 0)  # floor at 0


def priority_label(score: int) -> str:
    """Convert numeric score to a human-readable priority label."""
    if score >= 8:
        return "High"
    elif score >= 5:
        return "Medium"
    elif score >= MIN_SCORE:
        return "Low"
    return "Skip"


def extract_key_requirements(description: str, top_n: int = 6) -> str:
    """
    Pull the most relevant skill keywords found in the description
    and return them as a comma-separated string.
    """
    if not description:
        return ""
    blob = description.lower()
    found = []
    for kw in SKILL_KEYWORDS_POSITIVE:
        if re.search(r'\b' + re.escape(kw) + r'\b', blob):
            found.append(kw)
    return ", ".join(found[:top_n])
