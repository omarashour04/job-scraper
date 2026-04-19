"""
scrapers/wuzzuf.py — Scrapes Wuzzuf.net for job listings.

URL strategy:
  Search endpoint:  https://wuzzuf.net/search/jobs/?q={query}&filters[country_abbreviations][0]=EG
  Job detail URLs:  https://wuzzuf.net/jobs/p/<slug>-<id>

Root cause of wrong links:
  The original code picked up the first <a> in the card which is sometimes
  a company link or a category link, not the job title link.
  Fix: we explicitly filter for anchors whose href contains /jobs/p/ and
  excludes /company/, then derive both URL and title from that same element.
"""

import time
import logging
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

from config import SEARCH_QUERIES, REQUEST_DELAY_SEC, MAX_RESULTS_PER_QUERY

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

BASE_URL    = "https://wuzzuf.net/search/jobs/"
JOB_URL_RE  = re.compile(r"^/jobs/p/[^?#]+")   # matches /jobs/p/<slug> — no company or category


def _build_url(query: str) -> str:
    return (
        f"{BASE_URL}?q={quote_plus(query)}"
        "&a=navbg%7CTypehead"
        "&filters[country_abbreviations][0]=EG"
    )


def _detect_work_type(text: str) -> str:
    t = text.lower()
    if "remote" in t:
        return "Hybrid" if "hybrid" in t else "Remote"
    if "hybrid" in t:
        return "Hybrid"
    return "On-site"


def _get_job_anchor(card):
    """
    Return the <a> tag that links to the job detail page, or None.
    Wuzzuf job links: /jobs/p/<slug>-<numeric-id>
    We reject anything containing /company/, /search/, or /categories/.
    """
    for a in card.find_all("a", href=True):
        href = a["href"]
        if (
            href.startswith("/jobs/p/")
            and "/company/" not in href
            and "/search/" not in href
            and "/categories/" not in href
        ):
            return a
    return None


def _parse_cards(soup: BeautifulSoup, query: str) -> list[dict]:
    jobs = []
    cards = soup.find_all("article", class_=re.compile(r"css-"))[:MAX_RESULTS_PER_QUERY]
    if not cards:
        cards = soup.find_all("article")[:MAX_RESULTS_PER_QUERY]

    for card in cards:
        try:
            job_anchor = _get_job_anchor(card)
            if not job_anchor:
                continue

            # URL — strip tracking params, build absolute
            raw_href = job_anchor["href"].split("?")[0].split("#")[0]
            url = "https://wuzzuf.net" + raw_href if not raw_href.startswith("http") else raw_href

            # Title — text of that exact anchor
            title = job_anchor.get_text(strip=True)
            if not title:
                continue

            # Company — specifically the /company/ anchor
            company = ""
            for a in card.find_all("a", href=True):
                if "/company/" in a["href"]:
                    company = a.get_text(strip=True)
                    break

            # Location
            location = ""
            for span in card.find_all("span", class_=re.compile(r"css-")):
                txt = span.get_text(strip=True)
                if any(c in txt for c in ["Egypt", "Cairo", "Alexandria", "Remote", "Giza", "،"]):
                    location = txt
                    break

            tags_text = card.get_text(" ", strip=True)
            work_type = _detect_work_type(tags_text + " " + location)

            date_posted = ""
            for span in card.find_all("span"):
                txt = span.get_text(strip=True).lower()
                if any(w in txt for w in ["ago", "today", "yesterday", "hour", "day", "week"]):
                    date_posted = span.get_text(strip=True)
                    break

            jobs.append({
                "title":       title,
                "company":     company,
                "location":    location,
                "work_type":   work_type,
                "date_posted": date_posted,
                "url":         url,
                "description": tags_text,
                "source":      "Wuzzuf",
                "query":       query,
            })

        except Exception as exc:
            logger.debug("Wuzzuf card parse error: %s", exc)
            continue

    return jobs


def scrape_wuzzuf() -> list[dict]:
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
