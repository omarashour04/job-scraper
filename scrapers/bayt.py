"""
scrapers/bayt.py — Scrapes Bayt.com for job listings in Egypt.

URL strategy:
  Search endpoint: https://www.bayt.com/en/egypt/jobs/?q={query}
  Job detail URLs: https://www.bayt.com/en/egypt/jobs/<title>-job-<id>/
                   https://www.bayt.com/en/international/jobs/<title>-job-<id>/

Root cause of 404s:
  1. The old code used slug-based category URLs (/machine-learning-engineer-jobs/)
     which Bayt only generates for high-traffic categories — anything niche 404s.
     Fix: use the proper query-string search endpoint (?q=...) instead.
  2. Bayt job URLs must end with -job-<numeric-id>/ — any other pattern is a
     search/filter page or company page, not a job detail. The regex enforces this.
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
    "Referer": "https://www.bayt.com/",
}

BASE_URL = "https://www.bayt.com/en/egypt/jobs/"

# A valid Bayt job URL always ends with -job-<digits>/
# e.g. /en/egypt/jobs/machine-learning-engineer-job-4849302/
JOB_URL_RE = re.compile(r"/en/[a-z\-]+/jobs/[a-z0-9\-]+-job-(\d+)/?$")


def _build_url(query: str) -> str:
    return f"{BASE_URL}?q={quote_plus(query)}"


def _detect_work_type(text: str) -> str:
    t = text.lower()
    if "remote" in t:
        return "Hybrid" if "hybrid" in t else "Remote"
    if "hybrid" in t:
        return "Hybrid"
    return "On-site"


def _get_job_anchor(card):
    """
    Return the <a> that links to the specific job detail page.
    Valid pattern: /en/<country>/jobs/<title>-job-<id>/
    Reject: company pages, search pages, anything without -job-<id> at the end.
    """
    for a in card.find_all("a", href=True):
        href = a["href"].split("?")[0].rstrip("/") + "/"
        if JOB_URL_RE.search(href):
            return a
    return None


def _parse_cards(soup: BeautifulSoup, query: str) -> list[dict]:
    jobs = []

    # Bayt wraps each listing in <li data-js-job="...">
    cards = soup.find_all("li", attrs={"data-js-job": True})
    if not cards:
        # Fallback: any <li> with class containing "has-pointer"
        cards = soup.find_all("li", class_=re.compile(r"has-pointer"))
    cards = cards[:MAX_RESULTS_PER_QUERY]

    for card in cards:
        try:
            job_anchor = _get_job_anchor(card)
            if not job_anchor:
                continue

            # URL — strip ALL query params and fragments, keep only the path
            raw_href = job_anchor["href"].split("?")[0].split("#")[0]
            # Normalise trailing slash
            if not raw_href.endswith("/"):
                raw_href += "/"
            url = "https://www.bayt.com" + raw_href if not raw_href.startswith("http") else raw_href

            # Title — from the job anchor text, cleaned up
            title = job_anchor.get_text(strip=True)
            # Sometimes Bayt puts the title in a child <span> or <h2> nearby
            if not title or len(title) < 4:
                h = card.find("h2") or card.find("h3")
                title = h.get_text(strip=True) if h else ""
            if not title:
                continue

            # Company — look for a link to the company or employer page
            company = ""
            for a in card.find_all("a", href=True):
                href = a["href"]
                if "/company/" in href or "/employer/" in href or "/en/egypt/company/" in href:
                    company = a.get_text(strip=True)
                    break
            # Fallback: <b> or <span> with class containing "company"
            if not company:
                for tag in ["b", "span", "div"]:
                    el = card.find(tag, class_=re.compile(r"company|employer", re.I))
                    if el:
                        company = el.get_text(strip=True)
                        break

            # Location
            location = ""
            loc = card.find(class_=re.compile(r"location|loc\b", re.I))
            if loc:
                location = loc.get_text(strip=True)
            if not location:
                for span in card.find_all("span"):
                    txt = span.get_text(strip=True)
                    if any(c in txt for c in ["Egypt", "Cairo", "Alexandria", "Remote", "Giza"]):
                        location = txt
                        break

            card_text = card.get_text(" ", strip=True)
            work_type = _detect_work_type(card_text + " " + location)

            date_posted = ""
            date_tag = card.find(class_=re.compile(r"date|posted", re.I))
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
    all_jobs: list[dict] = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for query in SEARCH_QUERIES:
        url = _build_url(query)
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
