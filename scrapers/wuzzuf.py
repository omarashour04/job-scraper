"""
scrapers/wuzzuf.py — Scrapes Wuzzuf.net for job listings.

Uses requests + BeautifulSoup. Wuzzuf is scraper-friendly on its public
search pages (no mandatory login for reading job cards).

Search URL pattern:
    https://wuzzuf.net/search/jobs/?q={query}&a=navbg%7CTypehead&filters[country_abbreviations][0]=EG
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
}

BASE_URL = "https://wuzzuf.net/search/jobs/"


def _build_url(query: str) -> str:
    return (
        f"{BASE_URL}?q={quote_plus(query)}"
        "&a=navbg%7CTypehead"
        "&filters[country_abbreviations][0]=EG"
    )


def _detect_work_type(text: str) -> str:
    """Infer work arrangement from any available text."""
    t = text.lower()
    if "remote" in t:
        if "hybrid" in t:
            return "Hybrid"
        return "Remote"
    if "hybrid" in t:
        return "Hybrid"
    return "On-site"


def _parse_cards(soup: BeautifulSoup, query: str) -> list[dict]:
    """Parse job cards from a Wuzzuf search results page."""
    jobs = []
    # Wuzzuf wraps each job in an <article> with data-jobid or class css-1gatmva
    cards = soup.find_all("article", class_=re.compile(r"css-"))[:MAX_RESULTS_PER_QUERY]

    if not cards:
        # Fallback: look for any article tags
        cards = soup.find_all("article")[:MAX_RESULTS_PER_QUERY]

    for card in cards:
        try:
            # Title
            title_tag = card.find("h2") or card.find("h3")
            title = title_tag.get_text(strip=True) if title_tag else ""
            if not title:
                continue

            # URL
            link_tag = title_tag.find("a") if title_tag else card.find("a")
            url = ""
            if link_tag and link_tag.get("href"):
                href = link_tag["href"]
                url = href if href.startswith("http") else "https://wuzzuf.net" + href

            # Company
            company_tag = card.find("a", class_=re.compile(r"css-.*", re.I))
            company = ""
            for a in card.find_all("a"):
                href = a.get("href", "")
                if "/company/" in href or "/jobs/company/" in href:
                    company = a.get_text(strip=True)
                    break

            # Location
            location = ""
            loc_tags = card.find_all("span", class_=re.compile(r"css-"))
            for span in loc_tags:
                txt = span.get_text(strip=True)
                if any(c in txt for c in ["Egypt", "Cairo", "Alexandria", "Remote", "،"]):
                    location = txt
                    break

            # Work type & tags
            tags_text = card.get_text(" ", strip=True)
            work_type = _detect_work_type(tags_text + " " + location)

            # Date posted (Wuzzuf shows relative: "2 days ago")
            date_posted = ""
            for span in card.find_all("span"):
                txt = span.get_text(strip=True).lower()
                if "ago" in txt or "today" in txt or "yesterday" in txt:
                    date_posted = span.get_text(strip=True)
                    break

            jobs.append({
                "title":       title,
                "company":     company,
                "location":    location,
                "work_type":   work_type,
                "date_posted": date_posted,
                "url":         url,
                "description": tags_text,  # card text used for scoring
                "source":      "Wuzzuf",
                "query":       query,
            })

        except Exception as exc:
            logger.debug("Wuzzuf card parse error: %s", exc)
            continue

    return jobs


def scrape_wuzzuf() -> list[dict]:
    """Run all queries against Wuzzuf and return combined results."""
    all_jobs: list[dict] = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for query in SEARCH_QUERIES:
        url = _build_url(query)
        logger.info("Wuzzuf | query='%s' | %s", query, url)
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            jobs = _parse_cards(soup, query)
            logger.info("  → %d cards found", len(jobs))
            all_jobs.extend(jobs)
        except Exception as exc:
            logger.warning("Wuzzuf request failed for '%s': %s", query, exc)

        time.sleep(REQUEST_DELAY_SEC)

    return all_jobs
