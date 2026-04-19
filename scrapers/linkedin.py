"""
scrapers/linkedin.py — Scrapes LinkedIn public job search for listings.

LinkedIn's public job search (linkedin.com/jobs/search) does NOT require login
for reading job card summaries. However, it is more aggressive with bot detection
than Wuzzuf/Bayt. We use:
  - Randomised User-Agent rotation
  - Conservative request delays
  - The jobs/search API endpoint (JSON-backed, more stable than HTML scraping)

LinkedIn public API endpoint:
    https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
    ?keywords={query}&location={location}&start={offset}&count=25

This returns HTML fragments of job cards directly, parseable with BS4.

Geo codes used:
    Egypt                  → geoId=106155005
    Remote (worldwide)     → f_WT=2  (work type: remote)
    Hybrid                 → f_WT=3
"""

import time
import random
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

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

# (geo_label, geoId, work_type_filter)
# work_type: 1=onsite, 2=remote, 3=hybrid, None=any
SEARCH_TARGETS = [
    ("Egypt",          "106155005", None),   # all types in Egypt
    ("Remote Abroad",  None,        "2"),     # remote worldwide
]

LI_BASE = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"


def _build_url(query: str, geo_id: str | None, work_type: str | None, start: int = 0) -> str:
    params = [
        f"keywords={quote_plus(query)}",
        f"start={start}",
        "count=10",
        "sortBy=DD",  # date descending
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


def _parse_cards(html: str, query: str, geo_label: str) -> list[dict]:
    """Parse job card HTML fragments returned by LinkedIn's guest API."""
    soup = BeautifulSoup(html, "lxml")
    jobs = []

    # LinkedIn guest API returns <li> elements with class "jobs-search__results-list" items
    cards = soup.find_all("li")[:MAX_RESULTS_PER_QUERY]

    for card in cards:
        try:
            # Title
            title_tag = (
                card.find("h3", class_=re.compile(r"base-search-card__title"))
                or card.find("span", class_=re.compile(r"screen-reader-text"))
                or card.find("h3")
            )
            title = title_tag.get_text(strip=True) if title_tag else ""
            if not title or len(title) < 3:
                continue

            # URL — LinkedIn job detail link
            link_tag = card.find("a", class_=re.compile(r"base-card__full-link|result-card__full-card-link"))
            if not link_tag:
                link_tag = card.find("a", href=re.compile(r"/jobs/view/"))
            url = link_tag["href"].split("?")[0] if link_tag and link_tag.get("href") else ""

            # Company
            company_tag = card.find("h4", class_=re.compile(r"base-search-card__subtitle")) or card.find("a", class_=re.compile(r"hidden-nested-link"))
            company = company_tag.get_text(strip=True) if company_tag else ""

            # Location
            loc_tag = card.find("span", class_=re.compile(r"job-search-card__location"))
            location = loc_tag.get_text(strip=True) if loc_tag else geo_label

            # Date posted
            date_tag = card.find("time")
            date_posted = date_tag.get("datetime", date_tag.get_text(strip=True)) if date_tag else ""

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
    """Run all query × location combinations against LinkedIn guest API."""
    all_jobs: list[dict] = []
    session = requests.Session()

    for query in SEARCH_QUERIES:
        for geo_label, geo_id, work_type in SEARCH_TARGETS:
            ua = random.choice(USER_AGENTS)
            session.headers.update({
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.linkedin.com/jobs/search/",
            })

            url = _build_url(query, geo_id, work_type)
            logger.info("LinkedIn | query='%s' | target='%s' | %s", query, geo_label, url)
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
                logger.warning("LinkedIn request failed for '%s'/'%s': %s", query, geo_label, exc)

            # Longer delay for LinkedIn to avoid 429
            time.sleep(REQUEST_DELAY_SEC + random.uniform(1, 3))

    return all_jobs
