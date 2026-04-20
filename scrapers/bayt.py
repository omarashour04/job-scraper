"""
scrapers/bayt.py — Scrapes Bayt.com using Playwright.

headless=False is used because Cloudflare's bot detection blocks headless
Chromium even with playwright-stealth. A visible browser window passes all
checks. The window is minimised immediately so it does not interrupt work.
"""

import time
import logging
import re
import random
from urllib.parse import quote_plus

from config import SEARCH_QUERIES, MAX_RESULTS_PER_QUERY, PLAYWRIGHT_TIMEOUT

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

BASE_URL   = "https://www.bayt.com/en/egypt/jobs/"
JOB_URL_RE = re.compile(r"/en/[a-z\-]+/jobs/[a-z0-9\-]+-job-(\d+)/?")


def _build_url(query: str) -> str:
    return f"{BASE_URL}?q={quote_plus(query)}"


def _detect_work_type(text: str) -> str:
    t = text.lower()
    if "remote" in t:
        return "Hybrid" if "hybrid" in t else "Remote"
    if "hybrid" in t:
        return "Hybrid"
    return "On-site"


def _scrape_query(page, query: str) -> list[dict]:
    url = _build_url(query)
    jobs = []

    try:
        page.goto(url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="domcontentloaded")

        # Wait for Cloudflare challenge if present
        for _ in range(15):
            content = page.content()
            if "Just a moment" in content or "cf-browser-verification" in content:
                logger.debug("Bayt | Cloudflare — waiting...")
                time.sleep(1)
            else:
                break

        # Wait for job cards
        card_loaded = False
        for selector in ["li[data-js-job]", "li.has-pointer-d", "a[href*='-job-']"]:
            try:
                page.wait_for_selector(selector, timeout=8000)
                card_loaded = True
                break
            except Exception:
                continue

        if not card_loaded:
            logger.debug("Bayt | no cards for '%s'", query)
            return []

        anchors = page.query_selector_all("a[href*='-job-']")
        seen_urls = set()

        for anchor in anchors:
            try:
                href = anchor.get_attribute("href") or ""
                if not JOB_URL_RE.search(href):
                    continue
                if any(x in href for x in ["/company/", "/employer/", "/search", "?q="]):
                    continue

                clean_href = href.split("?")[0].rstrip("/") + "/"
                job_url = (
                    "https://www.bayt.com" + clean_href
                    if not clean_href.startswith("http")
                    else clean_href
                )

                if job_url in seen_urls:
                    continue
                seen_urls.add(job_url)
                if len(seen_urls) > MAX_RESULTS_PER_QUERY:
                    break

                title = (anchor.inner_text() or "").strip()
                if not title or len(title) < 4:
                    continue

                card_text = ""
                try:
                    card_text = page.evaluate("""
                        (el) => {
                            let p = el;
                            for (let i = 0; i < 6; i++) {
                                p = p.parentElement;
                                if (!p) break;
                                if (p.getAttribute && p.getAttribute('data-js-job'))
                                    return p.innerText;
                            }
                            return el.closest('li, article')?.innerText || '';
                        }
                    """, anchor.element_handle())
                except Exception:
                    card_text = title

                lines = [l.strip() for l in (card_text or "").split("\n") if l.strip()]
                company = lines[1] if len(lines) > 1 else ""

                location = ""
                for line in lines:
                    if any(c in line for c in ["Egypt", "Cairo", "Alexandria", "Remote", "Giza", "Hybrid"]):
                        location = line
                        break

                date_posted = ""
                for line in lines:
                    if any(w in line.lower() for w in ["ago", "today", "yesterday", "hour", "day", "week", "month"]):
                        date_posted = line
                        break

                work_type = _detect_work_type((card_text or "") + " " + location)

                jobs.append({
                    "title":       title,
                    "company":     company,
                    "location":    location,
                    "work_type":   work_type,
                    "date_posted": date_posted,
                    "url":         job_url,
                    "description": card_text or title,
                    "source":      "Bayt",
                    "query":       query,
                })

            except Exception as exc:
                logger.debug("Bayt anchor parse error: %s", exc)
                continue

    except Exception as exc:
        logger.warning("Bayt page error for '%s': %s", query, exc)

    return jobs


def scrape_bayt() -> list[dict]:
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
            # headless=False bypasses Cloudflare — window is minimised immediately
            browser = pw.chromium.launch(
                headless=False,
                args=["--no-sandbox", "--start-minimized"],
            )

            context = browser.new_context(
                user_agent=ua,
                viewport={"width": 1366, "height": 768},
                locale="en-US",
                timezone_id="Africa/Cairo",
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9,ar;q=0.8"},
            )

            page = context.new_page()
            stealth.apply_stealth_sync(page)

            # Minimise the window right away
            try:
                page.evaluate("window.resizeTo(0,0); window.moveTo(-2000,-2000);")
            except Exception:
                pass

            # Warm up
            logger.info("Bayt | warming up session...")
            try:
                page.goto("https://www.bayt.com/", timeout=20000, wait_until="domcontentloaded")
                for _ in range(15):
                    if "Just a moment" in page.content():
                        time.sleep(1)
                    else:
                        break
                time.sleep(3)
                logger.info("Bayt | session ready")
            except Exception as exc:
                logger.warning("Bayt warmup failed: %s", exc)

            for query in SEARCH_QUERIES:
                logger.info("Bayt | query='%s'", query)
                jobs = _scrape_query(page, query)
                logger.info("  → %d cards found", len(jobs))
                all_jobs.extend(jobs)
                time.sleep(random.uniform(1, 2))

            browser.close()

    except Exception as exc:
        logger.error("Bayt Playwright error: %s", exc, exc_info=True)

    return all_jobs
