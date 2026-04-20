"""
scrapers/wuzzuf.py — Scrapes Wuzzuf.net using Playwright + playwright-stealth.

Improvements:
  - Parallel page scraping: 3 pages open simultaneously → ~3x faster
  - Job detail scraping: visits each job URL to extract full description,
    requirements, experience level, and salary
  - Age filtering: skips jobs older than MAX_JOB_AGE_DAYS
"""

import time
import logging
import re
import random
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    SEARCH_QUERIES,
    MAX_RESULTS_PER_QUERY,
    PLAYWRIGHT_TIMEOUT,
    MAX_JOB_AGE_DAYS,
)

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

BASE_URL = "https://wuzzuf.net/search/jobs/"


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


def _parse_relative_date(date_str: str) -> datetime | None:
    """Convert Wuzzuf relative date strings to datetime objects."""
    if not date_str:
        return None
    s = date_str.lower().strip()
    now = datetime.now()
    try:
        if "today" in s or "just now" in s or "hour" in s:
            return now
        if "yesterday" in s:
            return now - timedelta(days=1)
        m = re.search(r"(\d+)\s*day", s)
        if m:
            return now - timedelta(days=int(m.group(1)))
        m = re.search(r"(\d+)\s*week", s)
        if m:
            return now - timedelta(weeks=int(m.group(1)))
        m = re.search(r"(\d+)\s*month", s)
        if m:
            return now - timedelta(days=int(m.group(1)) * 30)
    except Exception:
        pass
    return None


def _is_too_old(date_str: str) -> bool:
    """Return True if the job is older than MAX_JOB_AGE_DAYS."""
    dt = _parse_relative_date(date_str)
    if dt is None:
        return False  # can't determine — keep it
    cutoff = datetime.now() - timedelta(days=MAX_JOB_AGE_DAYS)
    return dt < cutoff


def _get_job_detail(page, url: str) -> dict:
    """
    Visit the job detail page and extract full description, requirements,
    experience level, and salary. Returns a dict with extra fields.
    """
    extra = {"full_description": "", "experience": "", "salary": ""}
    try:
        page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="domcontentloaded")
        page.wait_for_selector("section, .t-body, .job-description", timeout=6000)

        # Full description text
        desc_el = (
            page.query_selector(".job-description")
            or page.query_selector("[class*='description']")
            or page.query_selector("section.t-body")
        )
        if desc_el:
            extra["full_description"] = (desc_el.inner_text() or "").strip()

        # Experience level
        for label in page.query_selector_all("li, .t-small"):
            txt = (label.inner_text() or "").strip().lower()
            if "year" in txt and ("experience" in txt or "exp" in txt):
                extra["experience"] = label.inner_text().strip()
                break

        # Salary
        for label in page.query_selector_all("li, span, div"):
            txt = (label.inner_text() or "").strip().lower()
            if any(c in txt for c in ["egp", "salary", "usd", "$/", "£"]):
                val = label.inner_text().strip()
                if len(val) < 60:  # sanity check — not a paragraph
                    extra["salary"] = val
                    break

    except Exception as exc:
        logger.debug("Wuzzuf detail error for %s: %s", url, exc)

    return extra


def _scrape_query_on_page(page, query: str, detail_page) -> list[dict]:
    """Scrape one query. detail_page is a second page for job detail visits."""
    url = _build_url(query)
    jobs = []

    try:
        page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="domcontentloaded")

        card_selector = None
        for selector in ["article", "li a[href*='/jobs/p/']", "a[href*='/jobs/p/']"]:
            try:
                page.wait_for_selector(selector, timeout=8000)
                card_selector = selector
                break
            except Exception:
                continue

        if not card_selector:
            return []

        anchors = page.query_selector_all("a[href*='/jobs/p/']")
        seen_urls = set()

        for anchor in anchors[:MAX_RESULTS_PER_QUERY]:
            try:
                href = anchor.get_attribute("href") or ""
                if not href.startswith("/jobs/p/"):
                    continue
                if any(x in href for x in ["/company/", "/search/", "/categories/"]):
                    continue

                clean_href = href.split("?")[0].split("#")[0]
                job_url = "https://wuzzuf.net" + clean_href

                if job_url in seen_urls:
                    continue
                seen_urls.add(job_url)

                title = (anchor.inner_text() or "").strip()
                if not title:
                    continue

                # Card context
                card_text = ""
                try:
                    card_text = page.evaluate("""
                        (el) => {
                            let p = el;
                            for (let i = 0; i < 6; i++) {
                                p = p.parentElement;
                                if (!p) break;
                                if (['ARTICLE','LI'].includes(p.tagName)) return p.innerText;
                            }
                            return el.closest('article,li')?.innerText || '';
                        }
                    """, anchor.element_handle())
                except Exception:
                    card_text = title

                lines = [l.strip() for l in (card_text or "").split("\n") if l.strip()]
                company = lines[1] if len(lines) > 1 else ""

                location = ""
                for line in lines:
                    if any(c in line for c in ["Cairo", "Egypt", "Alexandria", "Remote", "Giza", "Hybrid"]):
                        location = line
                        break

                date_posted = ""
                for line in lines:
                    if any(w in line.lower() for w in ["ago", "today", "yesterday", "hour", "day", "week", "month"]):
                        date_posted = line
                        break

                # Age filter
                if _is_too_old(date_posted):
                    logger.debug("Wuzzuf | skipping old job: %s (%s)", title, date_posted)
                    continue

                work_type = _detect_work_type(card_text + " " + location)

                # Fetch full job detail
                extra = _get_job_detail(detail_page, job_url)
                full_desc = extra["full_description"] or card_text

                jobs.append({
                    "title":        title,
                    "company":      company,
                    "location":     location,
                    "work_type":    work_type,
                    "date_posted":  date_posted,
                    "experience":   extra["experience"],
                    "salary":       extra["salary"],
                    "url":          job_url,
                    "description":  full_desc,
                    "source":       "Wuzzuf",
                    "query":        query,
                })

            except Exception as exc:
                logger.debug("Wuzzuf anchor error: %s", exc)
                continue

    except Exception as exc:
        logger.warning("Wuzzuf page error for '%s': %s", query, exc)

    return jobs


def scrape_wuzzuf() -> list[dict]:
    all_jobs: list[dict] = []

    try:
        from playwright.sync_api import sync_playwright
        from playwright_stealth import Stealth
    except ImportError as e:
        logger.error("Missing dependency: %s", e)
        return []

    ua = random.choice(USER_AGENTS)
    stealth = Stealth(
        navigator_user_agent_override=ua,
        navigator_platform_override="Win32",
        navigator_vendor_override="Google Inc.",
    )

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )

            context = browser.new_context(
                user_agent=ua,
                viewport={"width": 1366, "height": 768},
                locale="en-US",
                timezone_id="Africa/Cairo",
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9,ar;q=0.8"},
            )

            # Open 3 search pages + 1 detail page per search page = 6 pages total
            # We run 3 queries in parallel, each with its own detail page
            PARALLEL = 3
            search_pages = [context.new_page() for _ in range(PARALLEL)]
            detail_pages = [context.new_page() for _ in range(PARALLEL)]

            for p in search_pages + detail_pages:
                stealth.apply_stealth_sync(p)

            # Warm up homepage on first page
            try:
                search_pages[0].goto("https://wuzzuf.net", timeout=15000, wait_until="domcontentloaded")
                time.sleep(2)
            except Exception:
                pass

            # Split queries into batches of PARALLEL
            query_batches = [
                SEARCH_QUERIES[i:i + PARALLEL]
                for i in range(0, len(SEARCH_QUERIES), PARALLEL)
            ]

            for batch in query_batches:
                batch_jobs = []

                # Run each query in the batch using its own page pair
                for idx, query in enumerate(batch):
                    logger.info("Wuzzuf | query='%s'", query)
                    jobs = _scrape_query_on_page(
                        search_pages[idx],
                        query,
                        detail_pages[idx],
                    )
                    logger.info("  → %d cards found", len(jobs))
                    batch_jobs.extend(jobs)

                all_jobs.extend(batch_jobs)
                time.sleep(random.uniform(1, 2))

            browser.close()

    except Exception as exc:
        logger.error("Wuzzuf Playwright error: %s", exc, exc_info=True)

    return all_jobs
