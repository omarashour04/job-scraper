"""
scrapers/remote_abroad.py — Scrapes remote-first international job boards.

Platforms:
  1. RemoteOK       — JSON API
  2. We Work Remotely (WWR) — Playwright (RSS feed blocked, using browser)
  3. Himalayas      — JSON API
  4. Jobicy         — JSON API

Two-layer relevance filter on all platforms:
  Layer 1: Title blocklist — rejects sales/marketing/HR roles
  Layer 2: Core ML title keyword — title must contain at least one ML/AI keyword
"""

import time
import logging
import re
import random
import requests
from xml.etree import ElementTree as ET
from datetime import datetime, timedelta

from config import (
    REQUEST_DELAY_SEC,
    SKILL_KEYWORDS_POSITIVE,
    REMOTE_TITLE_BLOCKLIST,
    REMOTE_CORE_TITLE_KEYWORDS,
    MAX_JOB_AGE_DAYS,
    PLAYWRIGHT_TIMEOUT,
)

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/xml, */*",
}


def _is_relevant(title: str) -> tuple[bool, str]:
    t = title.lower()
    for blocked in REMOTE_TITLE_BLOCKLIST:
        if blocked in t:
            return False, f"blocked: {blocked!r}"
    if not any(kw in t for kw in REMOTE_CORE_TITLE_KEYWORDS):
        return False, "no core ML keyword in title"
    return True, "ok"


def _has_skill_keywords(title: str, description: str) -> bool:
    blob = (title + " " + description).lower()
    return any(
        re.search(r'\b' + re.escape(kw) + r'\b', blob)
        for kw in SKILL_KEYWORDS_POSITIVE
    )


# ── RemoteOK ──────────────────────────────────────────────────────────────────

def _scrape_remoteok() -> list[dict]:
    logger.info("RemoteOK | fetching API")
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

            relevant, reason = _is_relevant(title)
            if not relevant:
                skipped += 1
                continue
            if not _has_skill_keywords(title, description):
                skipped += 1
                continue

            jobs.append({
                "title": title, "company": company,
                "location": "Remote (Worldwide)", "work_type": "Remote (Abroad)",
                "date_posted": date_posted, "url": url,
                "description": description, "source": "RemoteOK", "query": "remote_api",
            })

        logger.info("  → %d relevant | %d skipped", len(jobs), skipped)
    except Exception as exc:
        logger.warning("RemoteOK failed: %s", exc)
    return jobs


# ── We Work Remotely via Playwright ──────────────────────────────────────────

WWR_URLS = [
    ("https://weworkremotely.com/categories/remote-programming-jobs", "Programming"),
    ("https://weworkremotely.com/categories/remote-data-science-ai-jobs", "Data Science"),
]

def _scrape_wwr_playwright() -> list[dict]:
    """Scrape WWR using Playwright since their RSS feed is blocked."""
    jobs = []
    try:
        from playwright.sync_api import sync_playwright
        from playwright_stealth import Stealth
    except ImportError as e:
        logger.warning("WWR Playwright unavailable: %s", e)
        return []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
                viewport={"width": 1366, "height": 768},
                locale="en-US",
            )
            page = context.new_page()
            Stealth().apply_stealth_sync(page)

            for url, category in WWR_URLS:
                logger.info("WWR | %s", category)
                try:
                    page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="domcontentloaded")
                    page.wait_for_selector("li.feature, li.job, .jobs-container li", timeout=8000)

                    job_els = page.query_selector_all("li.feature, li.job")
                    skipped = 0

                    for el in job_els:
                        try:
                            text = (el.inner_text() or "").strip()
                            lines = [l.strip() for l in text.split("\n") if l.strip()]
                            if len(lines) < 2:
                                continue

                            # WWR format: Company / Title / Location
                            company = lines[0] if lines else ""
                            title   = lines[1] if len(lines) > 1 else lines[0]
                            location = lines[2] if len(lines) > 2 else "Remote"

                            # URL
                            link = el.query_selector("a")
                            href = link.get_attribute("href") if link else ""
                            job_url = "https://weworkremotely.com" + href if href and not href.startswith("http") else href

                            relevant, reason = _is_relevant(title)
                            if not relevant:
                                skipped += 1
                                continue
                            if not _has_skill_keywords(title, text):
                                skipped += 1
                                continue

                            jobs.append({
                                "title": title, "company": company,
                                "location": f"Remote — {location}", "work_type": "Remote (Abroad)",
                                "date_posted": "", "url": job_url,
                                "description": text, "source": "WeWorkRemotely", "query": category,
                            })
                        except Exception:
                            continue

                    logger.info("  → %d relevant | %d skipped (%s)", len(jobs), skipped, category)

                except Exception as exc:
                    logger.warning("WWR page error for %s: %s", category, exc)

                time.sleep(REQUEST_DELAY_SEC)

            browser.close()

    except Exception as exc:
        logger.error("WWR Playwright error: %s", exc)

    return jobs


# ── Himalayas ─────────────────────────────────────────────────────────────────

def _scrape_himalayas() -> list[dict]:
    jobs = []
    queries = ["machine learning", "computer vision", "deep learning", "nlp", "data scientist", "ai engineer"]
    for query in queries:
        url = f"https://himalayas.app/jobs/api?q={query}&limit=30"
        logger.info("Himalayas | query='%s'", query)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            listings = resp.json().get("jobs", [])
            skipped = 0
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
                    continue
                if not _has_skill_keywords(title, description):
                    skipped += 1
                    continue

                jobs.append({
                    "title": title, "company": company,
                    "location": location, "work_type": "Remote (Abroad)",
                    "date_posted": date_posted, "url": job_url,
                    "description": description, "source": "Himalayas", "query": query,
                })
            logger.info("  → %d relevant | %d skipped (query=%s)", len(jobs), skipped, query)
        except Exception as exc:
            logger.warning("Himalayas '%s' failed: %s", query, exc)
        time.sleep(REQUEST_DELAY_SEC)
    return jobs


# ── Jobicy ────────────────────────────────────────────────────────────────────

def _scrape_jobicy() -> list[dict]:
    jobs = []
    tags = ["machine-learning", "data-science", "computer-vision", "nlp", "python"]
    for tag in tags:
        url = f"https://jobicy.com/api/v2/remote-jobs?count=30&tag={tag}"
        logger.info("Jobicy | tag='%s'", tag)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            listings = resp.json().get("jobs", [])
            skipped = 0
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
                    continue
                if not _has_skill_keywords(title, description):
                    skipped += 1
                    continue

                jobs.append({
                    "title": title, "company": company,
                    "location": location, "work_type": "Remote (Abroad)",
                    "date_posted": date_posted, "url": job_url,
                    "description": description, "source": "Jobicy", "query": tag,
                })
            logger.info("  → %d relevant | %d skipped (tag=%s)", len(jobs), skipped, tag)
        except Exception as exc:
            logger.warning("Jobicy '%s' failed: %s", tag, exc)
        time.sleep(REQUEST_DELAY_SEC)
    return jobs


def scrape_remote_abroad() -> list[dict]:
    results = []
    results.extend(_scrape_remoteok())
    results.extend(_scrape_wwr_playwright())
    results.extend(_scrape_himalayas())
    results.extend(_scrape_jobicy())
    return results
