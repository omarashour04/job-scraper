"""
scrapers/bayt.py — Scrapes Bayt.com for job listings in Egypt.

Uses requests + BeautifulSoup. Bayt's job search is publicly accessible.

Search URL pattern:
    https://www.bayt.com/en/egypt/jobs/{query}-jobs/
    e.g.: https://www.bayt.com/en/egypt/jobs/machine-learning-engineer-jobs/
"""

import time
import logging
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

from config import (
    SEARCH_QUERIES,
    REQUEST_DELAY_SEC,
    MAX_RESULTS_PER_QUERY,
)

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.bayt.com/",
}

BASE_URL = "https://www.bayt.com/en/egypt/jobs/"


def _query_to_slug(query: str) -> str:
    """Convert a search query to Bayt's slug format: 'ML Engineer' → 'ml-engineer-jobs'"""
    slug = re.sub(r"[^a-zA-Z0-9 ]", "", query).strip().lower()
    slug = re.sub(r"\s+", "-", slug)
    return f"{slug}-jobs"


def _detect_work_type(text: str) -> str:
    t = text.lower()
    if "remote" in t:
        return "Hybrid" if "hybrid" in t else "Remote"
    if "hybrid" in t:
        return "Hybrid"
    return "On-site"


def _parse_cards(soup: BeautifulSoup, query: str) -> list[dict]:
    """Extract job listings from a Bayt search results page."""
    jobs = []

    # Bayt uses <li> with data-js-job or class="has-pointer-d"
    cards = (
        soup.find_all("li", attrs={"data-js-job": True})
        or soup.find_all("li", class_=re.compile(r"has-pointer"))
    )
    cards = cards[:MAX_RESULTS_PER_QUERY]

    for card in cards:
        try:
            # Title + URL
            title_tag = card.find("a", attrs={"data-js-aid": True}) or card.find("h2") or card.find("h3")
            title = title_tag.get_text(strip=True) if title_tag else ""
            if not title:
                continue

            url = ""
            if title_tag and title_tag.name == "a":
                href = title_tag.get("href", "")
                url = href if href.startswith("http") else "https://www.bayt.com" + href
            else:
                link = card.find("a", href=re.compile(r"/jobs/"))
                if link:
                    href = link.get("href", "")
                    url = href if href.startswith("http") else "https://www.bayt.com" + href

            # Company
            company = ""
            company_tag = card.find("b", class_=re.compile(r"jb-company"))
            if not company_tag:
                company_tag = card.find("span", class_=re.compile(r"company"))
            if company_tag:
                company = company_tag.get_text(strip=True)

            # Location
            location = ""
            loc_tag = card.find("span", class_=re.compile(r"location|jb-loc"))
            if loc_tag:
                location = loc_tag.get_text(strip=True)

            # Full card text for work type detection
            card_text = card.get_text(" ", strip=True)
            work_type = _detect_work_type(card_text + " " + location)

            # Date posted
            date_posted = ""
            date_tag = card.find("span", class_=re.compile(r"date|posted|ago"))
            if date_tag:
                date_posted = date_tag.get_text(strip=True)

            jobs.append({
                "title":       title,
                "company":     company,
                "location":    location,
                "work_type":   work_type,
                "date_posted": date_posted,
                "url":         url,
                "description": card_text,
                "source":      "Bayt",
                "query":       query,
            })

        except Exception as exc:
            logger.debug("Bayt card parse error: %s", exc)
            continue

    return jobs


def scrape_bayt() -> list[dict]:
    """Run all queries against Bayt and return combined results."""
    all_jobs: list[dict] = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for query in SEARCH_QUERIES:
        slug = _query_to_slug(query)
        url = BASE_URL + slug + "/"
        logger.info("Bayt | query='%s' | %s", query, url)
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            jobs = _parse_cards(soup, query)
            logger.info("  → %d cards found", len(jobs))
            all_jobs.extend(jobs)
        except Exception as exc:
            logger.warning("Bayt request failed for '%s': %s", query, exc)

        time.sleep(REQUEST_DELAY_SEC)

    return all_jobs
