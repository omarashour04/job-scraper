"""
scrapers/remote_abroad.py — Scrapes remote-first international job boards.

Platforms covered:
  1. RemoteOK       — JSON API (very clean, no auth required)
  2. We Work Remotely (WWR) — RSS feed (XML)
  3. Himalayas.app  — JSON API
  4. Jobicy.com     — JSON API (remote jobs globally)

All four platforms have public, documented APIs or feeds — no scraping tricks
needed. We filter results post-fetch using the skill keyword list.
"""

import time
import logging
import re
import requests
from xml.etree import ElementTree as ET

from config import (
    SEARCH_QUERIES,
    REQUEST_DELAY_SEC,
    SKILL_KEYWORDS_POSITIVE,
)

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0; +https://github.com/omarashour04)",
    "Accept": "application/json, text/xml, */*",
}

# ──────────────────────────────────────────────────────────────────────────────
#  RemoteOK  (JSON API)
#  https://remoteok.com/api
# ──────────────────────────────────────────────────────────────────────────────

def _scrape_remoteok() -> list[dict]:
    logger.info("RemoteOK | fetching public API")
    jobs = []
    try:
        resp = requests.get("https://remoteok.com/api", headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        # First element is a legal notice dict, skip it
        listings = [item for item in data if isinstance(item, dict) and item.get("position")]

        for item in listings:
            title       = item.get("position", "")
            company     = item.get("company", "")
            tags        = " ".join(item.get("tags", []))
            description = item.get("description", "") + " " + tags
            url         = item.get("url", "")
            date_posted = item.get("date", "")

            # Filter: must match at least one of our skill keywords
            blob = (title + " " + description).lower()
            if not any(re.search(r'\b' + re.escape(kw) + r'\b', blob) for kw in SKILL_KEYWORDS_POSITIVE):
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

        logger.info("  → %d relevant listings after keyword filter", len(jobs))
    except Exception as exc:
        logger.warning("RemoteOK failed: %s", exc)

    return jobs


# ──────────────────────────────────────────────────────────────────────────────
#  We Work Remotely  (RSS)
#  https://weworkremotely.com/remote-jobs.rss
#  Category feeds:
#    /categories/2-programming/jobs.rss
#    /categories/7-data-science/jobs.rss
# ──────────────────────────────────────────────────────────────────────────────

WWR_FEEDS = [
    ("https://weworkremotely.com/categories/2-programming/jobs.rss",   "Programming"),
    ("https://weworkremotely.com/categories/7-data-science/jobs.rss",  "Data Science"),
]

def _scrape_wwr() -> list[dict]:
    jobs = []
    for feed_url, category in WWR_FEEDS:
        logger.info("WWR | feed='%s'", feed_url)
        try:
            resp = requests.get(feed_url, headers={**HEADERS, "Accept": "application/rss+xml"}, timeout=20)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            ns = {"dc": "http://purl.org/dc/elements/1.1/"}

            for item in root.iter("item"):
                title_el   = item.find("title")
                link_el    = item.find("link")
                desc_el    = item.find("description")
                pubdate_el = item.find("pubDate")
                region_el  = item.find("region")

                title       = title_el.text.strip() if title_el is not None else ""
                url         = link_el.text.strip() if link_el is not None else ""
                description = re.sub(r"<[^>]+>", " ", desc_el.text or "") if desc_el is not None else ""
                date_posted = pubdate_el.text.strip() if pubdate_el is not None else ""
                region      = region_el.text.strip() if region_el is not None else "Worldwide"

                # Parse company from title (WWR format: "Company: Role Title")
                company = ""
                if ": " in title:
                    parts = title.split(": ", 1)
                    company, title = parts[0].strip(), parts[1].strip()

                blob = (title + " " + description).lower()
                if not any(re.search(r'\b' + re.escape(kw) + r'\b', blob) for kw in SKILL_KEYWORDS_POSITIVE):
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

        except Exception as exc:
            logger.warning("WWR feed '%s' failed: %s", feed_url, exc)

        time.sleep(REQUEST_DELAY_SEC)

    logger.info("  → %d relevant WWR listings", len(jobs))
    return jobs


# ──────────────────────────────────────────────────────────────────────────────
#  Himalayas.app  (JSON API)
#  https://himalayas.app/jobs/api?q={query}&limit=50
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
            data = resp.json()
            listings = data.get("jobs", [])
            for item in listings:
                title       = item.get("title", "")
                company     = item.get("company", {}).get("name", "")
                location    = item.get("locations", ["Remote"])[0] if item.get("locations") else "Remote"
                date_posted = item.get("createdAt", "")
                description = item.get("description", "") or item.get("responsibilities", "")
                job_url     = item.get("applicationLink", "") or item.get("url", "")

                blob = (title + " " + description).lower()
                if not any(re.search(r'\b' + re.escape(kw) + r'\b', blob) for kw in SKILL_KEYWORDS_POSITIVE):
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

        except Exception as exc:
            logger.warning("Himalayas query '%s' failed: %s", query, exc)

        time.sleep(REQUEST_DELAY_SEC)

    logger.info("  → %d relevant Himalayas listings", len(jobs))
    return jobs


# ──────────────────────────────────────────────────────────────────────────────
#  Jobicy  (JSON API — remote jobs globally)
#  https://jobicy.com/api/v2/remote-jobs?count=50&tag={tag}
# ──────────────────────────────────────────────────────────────────────────────

def _scrape_jobicy() -> list[dict]:
    jobs = []
    tags = ["machine-learning", "data-science", "python", "computer-vision", "nlp"]
    for tag in tags:
        url = f"https://jobicy.com/api/v2/remote-jobs?count=30&tag={tag}"
        logger.info("Jobicy | tag='%s'", tag)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            listings = data.get("jobs", [])
            for item in listings:
                title       = item.get("jobTitle", "")
                company     = item.get("companyName", "")
                location    = item.get("jobGeo", "Remote")
                date_posted = item.get("pubDate", "")
                description = item.get("jobDescription", "")
                job_url     = item.get("url", "")

                blob = (title + " " + description).lower()
                if not any(re.search(r'\b' + re.escape(kw) + r'\b', blob) for kw in SKILL_KEYWORDS_POSITIVE):
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

        except Exception as exc:
            logger.warning("Jobicy tag '%s' failed: %s", tag, exc)

        time.sleep(REQUEST_DELAY_SEC)

    logger.info("  → %d relevant Jobicy listings", len(jobs))
    return jobs


# ──────────────────────────────────────────────────────────────────────────────
#  Public entry point
# ──────────────────────────────────────────────────────────────────────────────

def scrape_remote_abroad() -> list[dict]:
    """Aggregate all remote-abroad platforms and return combined results."""
    results = []
    results.extend(_scrape_remoteok())
    results.extend(_scrape_wwr())
    results.extend(_scrape_himalayas())
    results.extend(_scrape_jobicy())
    return results
