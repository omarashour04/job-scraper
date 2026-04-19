"""
scrapers/linkedin.py — Scrapes LinkedIn public job search for listings.

Uses the public guest API (no login required for card-level data).

Root cause of broken links:
  LinkedIn job card anchors contain massive tracking query strings:
    https://www.linkedin.com/jobs/view/3912345678/?refId=abc123&trackingId=xyz&...
  When clicked, LinkedIn's redirect chain sometimes lands on an unrelated page
  if the tracking params are malformed or expired.

  Fix: extract only the numeric job ID from any href, then build the clean
  canonical URL ourselves:
    https://www.linkedin.com/jobs/view/<id>/

  This URL format is permanent and never redirects.
"""

import time
import random
import logging
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

from config import SEARCH_QUERIES, REQUEST_DELAY_SEC, MAX_RESULTS_PER_QUERY

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

# (label, geoId for Egypt, work_type filter)
SEARCH_TARGETS = [
    ("Egypt",         "106155005", None),   # all types in Egypt
    ("Remote Abroad", None,        "2"),    # remote worldwide
]

LI_BASE   = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
JOB_ID_RE = re.compile(r"/jobs/view/(\d{6,})")   # LinkedIn job IDs are 6+ digits


def _build_url(query: str, geo_id, work_type, start: int = 0) -> str:
    params = [
        f"keywords={quote_plus(query)}",
        f"start={start}",
        "count=10",
        "sortBy=DD",
    ]
    if geo_id:
        params.append(f"geoId={geo_id}")
    if work_type:
        params.append(f"f_WT={work_type}")
    return LI_BASE + "?" + "&".join(params)


def _detect_work_type(text: str) -> str:
    t = text.lower()
    if "remote" in t:
        return "Hybrid" if "hybrid" in t else "Remote"
    if "hybrid" in t:
        return "Hybrid"
    return "On-site"


def _clean_linkedin_url(href: str) -> str:
    """
    Extract the numeric job ID from any LinkedIn href and return the
    clean canonical URL with no tracking parameters.

    Examples:
      Input:  /jobs/view/3912345678/?refId=abc&trackingId=xyz
      Input:  https://eg.linkedin.com/jobs/view/3912345678?trk=something
      Output: https://www.linkedin.com/jobs/view/3912345678/
    """
    m = JOB_ID_RE.search(href)
    if m:
        return f"https://www.linkedin.com/jobs/view/{m.group(1)}/"
    return ""


def _parse_cards(html: str, query: str, geo_label: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    jobs = []
    cards = soup.find_all("li")[:MAX_RESULTS_PER_QUERY]

    for card in cards:
        try:
            # URL — scan every anchor, take the first one with a valid job ID
            url = ""
            for a in card.find_all("a", href=True):
                candidate = _clean_linkedin_url(a["href"])
                if candidate:
                    url = candidate
                    break
            if not url:
                continue   # card has no valid job link — skip it

            # Title
            title_tag = (
                card.find("h3", class_=re.compile(r"base-search-card__title"))
                or card.find("h3")
                or card.find("span", class_=re.compile(r"screen-reader-text"))
            )
            title = title_tag.get_text(strip=True) if title_tag else ""
            if not title or len(title) < 3:
                continue

            # Company
            company_tag = (
                card.find("h4", class_=re.compile(r"base-search-card__subtitle"))
                or card.find("a", class_=re.compile(r"hidden-nested-link"))
            )
            company = company_tag.get_text(strip=True) if company_tag else ""

            # Location
            loc_tag = card.find("span", class_=re.compile(r"job-search-card__location"))
            location = loc_tag.get_text(strip=True) if loc_tag else geo_label

            # Date posted — LinkedIn uses a <time datetime="YYYY-MM-DD"> element
            date_tag = card.find("time")
            date_posted = date_tag.get("datetime", "") if date_tag else ""

            card_text = card.get_text(" ", strip=True)
            work_type = _detect_work_type(card_text + " " + location)
            if geo_label == "Remote Abroad" and "Remote" not in work_type:
                work_type = "Remote (Abroad)"

            jobs.append({
                "title":       title,
                "company":     company,
                "location":    location,
                "work_type":   work_type,
                "date_posted": date_posted,
                "url":         url,
                "description": card_text,
                "source":      "LinkedIn",
                "query":       query,
            })

        except Exception as exc:
            logger.debug("LinkedIn card parse error: %s", exc)
            continue

    return jobs


def scrape_linkedin() -> list[dict]:
    all_jobs: list[dict] = []
    session = requests.Session()

    for query in SEARCH_QUERIES:
        for geo_label, geo_id, work_type in SEARCH_TARGETS:
            session.headers.update({
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.linkedin.com/jobs/search/",
            })

            url = _build_url(query, geo_id, work_type)
            logger.info("LinkedIn | query='%s' | target='%s'", query, geo_label)
            try:
                resp = session.get(url, timeout=20)
                if resp.status_code == 429:
                    logger.warning("LinkedIn rate-limited — sleeping 30s")
                    time.sleep(30)
                    continue
                resp.raise_for_status()
                jobs = _parse_cards(resp.text, query, geo_label)
                logger.info("  → %d cards found", len(jobs))
                all_jobs.extend(jobs)
            except Exception as exc:
                logger.warning("LinkedIn failed for '%s'/'%s': %s", query, geo_label, exc)

            time.sleep(REQUEST_DELAY_SEC + random.uniform(1, 3))

    return all_jobs
