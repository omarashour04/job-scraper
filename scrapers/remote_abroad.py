"""
scrapers/remote_abroad.py — Scrapes remote-first international job boards.

Platforms:
  1. RemoteOK       — JSON API
  2. We Work Remotely (WWR) — RSS feed
  3. Himalayas.app  — JSON API
  4. Jobicy.com     — JSON API

Root cause of irrelevant results (e.g. "Remote Local Advertising Account Executive"):
  These platforms return ALL remote jobs — not just tech/ML roles. The previous
  filter only checked if any skill keyword appeared anywhere in the description.
  Generic keywords like "python", "sql", "entry level", "docker" appear in sales,
  marketing, and operations job descriptions, letting them pass.

Fix — two-layer filter applied to every listing from these APIs:
  Layer 1: TITLE BLOCKLIST — reject immediately if title contains any sales/
           marketing/non-tech role indicator. Fast and catches the obvious cases.
  Layer 2: CORE ML TITLE KEYWORDS — the job title must contain at least one
           ML/AI/data keyword. Description keyword matches alone are insufficient.
  The existing scoring engine then runs on anything that passes both layers.
"""

import time
import logging
import re
import requests
from xml.etree import ElementTree as ET

from config import (
    REQUEST_DELAY_SEC,
    SKILL_KEYWORDS_POSITIVE,
    REMOTE_TITLE_BLOCKLIST,
    REMOTE_CORE_TITLE_KEYWORDS,
)

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/xml, */*",
}


def _is_relevant(title: str) -> tuple[bool, str]:
    """
    Two-layer title-level relevance check for remote API results.

    Returns (is_relevant, reason_string).
    """
    t = title.lower()

    # Layer 1: hard blocklist
    for blocked in REMOTE_TITLE_BLOCKLIST:
        if blocked in t:
            return False, f"blocked: {blocked!r}"

    # Layer 2: must contain a core ML/AI keyword in title
    if not any(kw in t for kw in REMOTE_CORE_TITLE_KEYWORDS):
        return False, "no core ML keyword in title"

    return True, "ok"


# ──────────────────────────────────────────────────────────────────────────────
#  RemoteOK
# ──────────────────────────────────────────────────────────────────────────────

def _scrape_remoteok() -> list[dict]:
    logger.info("RemoteOK | fetching public API")
    jobs = []
    try:
        resp = requests.get("https://remoteok.com/api", headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        listings = [item for item in data if isinstance(item, dict) and item.get("position")]

        skipped = 0
        for item in listings:
            title       = item.get("position", "")
            company     = item.get("company", "")
            tags        = " ".join(item.get("tags", []))
            description = (item.get("description", "") or "") + " " + tags
            url         = item.get("url", "")
            date_posted = item.get("date", "")

            # Two-layer title filter
            relevant, reason = _is_relevant(title)
            if not relevant:
                skipped += 1
                logger.debug("RemoteOK skip [%s]: %r", reason, title)
                continue

            # Secondary: description must also have at least one skill keyword
            blob = (title + " " + description).lower()
            if not any(re.search(r'\b' + re.escape(kw) + r'\b', blob)
                       for kw in SKILL_KEYWORDS_POSITIVE):
                skipped += 1
                continue

            jobs.append({
                "title":       title,
                "company":     company,
                "location":    "Remote (Worldwide)",
                "work_type":   "Remote (Abroad)",
                "date_posted": date_posted,
                "url":         url,
                "description": description,
                "source":      "RemoteOK",
                "query":       "remote_api",
            })

        logger.info("  → %d relevant | %d skipped", len(jobs), skipped)
    except Exception as exc:
        logger.warning("RemoteOK failed: %s", exc)

    return jobs


# ──────────────────────────────────────────────────────────────────────────────
#  We Work Remotely (RSS)
# ──────────────────────────────────────────────────────────────────────────────

WWR_FEEDS = [
    ("https://weworkremotely.com/categories/2-programming/jobs.rss",  "Programming"),
    ("https://weworkremotely.com/categories/7-data-science/jobs.rss", "Data Science"),
]

def _scrape_wwr() -> list[dict]:
    jobs = []
    for feed_url, category in WWR_FEEDS:
        logger.info("WWR | feed='%s'", feed_url)
        try:
            resp = requests.get(
                feed_url,
                headers={**HEADERS, "Accept": "application/rss+xml"},
                timeout=20,
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            skipped = 0
            for item in root.iter("item"):
                title_el   = item.find("title")
                link_el    = item.find("link")
                desc_el    = item.find("description")
                pubdate_el = item.find("pubDate")
                region_el  = item.find("region")

                raw_title   = title_el.text.strip() if title_el is not None else ""
                url         = link_el.text.strip() if link_el is not None else ""
                description = re.sub(r"<[^>]+>", " ", desc_el.text or "") if desc_el is not None else ""
                date_posted = pubdate_el.text.strip() if pubdate_el is not None else ""
                region      = region_el.text.strip() if region_el is not None else "Worldwide"

                # WWR format: "CompanyName: Job Title"
                company = ""
                title   = raw_title
                if ": " in raw_title:
                    parts   = raw_title.split(": ", 1)
                    company = parts[0].strip()
                    title   = parts[1].strip()

                relevant, reason = _is_relevant(title)
                if not relevant:
                    skipped += 1
                    logger.debug("WWR skip [%s]: %r", reason, title)
                    continue

                blob = (title + " " + description).lower()
                if not any(re.search(r'\b' + re.escape(kw) + r'\b', blob)
                           for kw in SKILL_KEYWORDS_POSITIVE):
                    skipped += 1
                    continue

                jobs.append({
                    "title":       title,
                    "company":     company,
                    "location":    f"Remote — {region}",
                    "work_type":   "Remote (Abroad)",
                    "date_posted": date_posted,
                    "url":         url,
                    "description": description,
                    "source":      "WeWorkRemotely",
                    "query":       category,
                })

            logger.info("  → %d relevant | %d skipped (%s)", len(jobs), skipped, category)

        except Exception as exc:
            logger.warning("WWR feed '%s' failed: %s", feed_url, exc)

        time.sleep(REQUEST_DELAY_SEC)

    return jobs


# ──────────────────────────────────────────────────────────────────────────────
#  Himalayas
# ──────────────────────────────────────────────────────────────────────────────

def _scrape_himalayas() -> list[dict]:
    jobs = []
    queries_to_run = [
        "machine learning", "computer vision", "deep learning",
        "nlp", "data scientist", "ai engineer",
    ]
    for query in queries_to_run:
        url = f"https://himalayas.app/jobs/api?q={query}&limit=30"
        logger.info("Himalayas | query='%s'", query)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data     = resp.json()
            listings = data.get("jobs", [])
            skipped  = 0

            for item in listings:
                title       = item.get("title", "")
                company     = item.get("company", {}).get("name", "")
                location    = (item.get("locations") or ["Remote"])[0]
                date_posted = item.get("createdAt", "")
                description = item.get("description", "") or item.get("responsibilities", "") or ""
                job_url     = item.get("applicationLink", "") or item.get("url", "")

                relevant, reason = _is_relevant(title)
                if not relevant:
                    skipped += 1
                    logger.debug("Himalayas skip [%s]: %r", reason, title)
                    continue

                blob = (title + " " + description).lower()
                if not any(re.search(r'\b' + re.escape(kw) + r'\b', blob)
                           for kw in SKILL_KEYWORDS_POSITIVE):
                    skipped += 1
                    continue

                jobs.append({
                    "title":       title,
                    "company":     company,
                    "location":    location,
                    "work_type":   "Remote (Abroad)",
                    "date_posted": date_posted,
                    "url":         job_url,
                    "description": description,
                    "source":      "Himalayas",
                    "query":       query,
                })

            logger.info("  → %d relevant | %d skipped (query=%s)", len(jobs), skipped, query)

        except Exception as exc:
            logger.warning("Himalayas query '%s' failed: %s", query, exc)

        time.sleep(REQUEST_DELAY_SEC)

    return jobs


# ──────────────────────────────────────────────────────────────────────────────
#  Jobicy
# ──────────────────────────────────────────────────────────────────────────────

def _scrape_jobicy() -> list[dict]:
    jobs = []
    tags = ["machine-learning", "data-science", "computer-vision", "nlp", "python"]
    for tag in tags:
        url = f"https://jobicy.com/api/v2/remote-jobs?count=30&tag={tag}"
        logger.info("Jobicy | tag='%s'", tag)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data     = resp.json()
            listings = data.get("jobs", [])
            skipped  = 0

            for item in listings:
                title       = item.get("jobTitle", "")
                company     = item.get("companyName", "")
                location    = item.get("jobGeo", "Remote")
                date_posted = item.get("pubDate", "")
                description = item.get("jobDescription", "") or ""
                job_url     = item.get("url", "")

                relevant, reason = _is_relevant(title)
                if not relevant:
                    skipped += 1
                    logger.debug("Jobicy skip [%s]: %r", reason, title)
                    continue

                blob = (title + " " + description).lower()
                if not any(re.search(r'\b' + re.escape(kw) + r'\b', blob)
                           for kw in SKILL_KEYWORDS_POSITIVE):
                    skipped += 1
                    continue

                jobs.append({
                    "title":       title,
                    "company":     company,
                    "location":    location,
                    "work_type":   "Remote (Abroad)",
                    "date_posted": date_posted,
                    "url":         job_url,
                    "description": description,
                    "source":      "Jobicy",
                    "query":       tag,
                })

            logger.info("  → %d relevant | %d skipped (tag=%s)", len(jobs), skipped, tag)

        except Exception as exc:
            logger.warning("Jobicy tag '%s' failed: %s", tag, exc)

        time.sleep(REQUEST_DELAY_SEC)

    return jobs


# ──────────────────────────────────────────────────────────────────────────────
#  Public entry point
# ──────────────────────────────────────────────────────────────────────────────

def scrape_remote_abroad() -> list[dict]:
    results = []
    results.extend(_scrape_remoteok())
    results.extend(_scrape_wwr())
    results.extend(_scrape_himalayas())
    results.extend(_scrape_jobicy())
    return results
