"""
main.py — Orchestrates the full job search pipeline.

Key features:
  - Incremental saving: writes to Excel after each scraper finishes
    so Ctrl+C never loses already-scraped data
  - Auto-opens Excel after run so you see results immediately
  - --quick skips LinkedIn (rate-limits aggressively)
"""

import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import LOG_FILE, MIN_SCORE, NOTIFICATION_TITLE, NOTIFICATION_TIMEOUT, EXCEL_FILE
from scorer import score_job, extract_key_requirements, priority_label
from deduplicator import filter_new
from excel_writer import append_jobs
from notifier import notify


def _setup_logging() -> None:
    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ],
    )

logger = logging.getLogger("main")


def _get_scrapers(platform: str | None, quick: bool) -> list[tuple[str, callable]]:
    from scrapers.wuzzuf        import scrape_wuzzuf
    from scrapers.bayt          import scrape_bayt
    from scrapers.linkedin      import scrape_linkedin
    from scrapers.remote_abroad import scrape_remote_abroad

    all_scrapers = [
        ("LinkedIn",      scrape_linkedin),
        ("Wuzzuf",        scrape_wuzzuf),
        ("Bayt",          scrape_bayt),
        ("Remote Abroad", scrape_remote_abroad),
    ]

    quick_scrapers = [
        ("Wuzzuf",        scrape_wuzzuf),
        ("Bayt",          scrape_bayt),
        ("Remote Abroad", scrape_remote_abroad),
    ]

    if platform:
        mapping = {s[0].lower(): s for s in all_scrapers}
        key = platform.lower()
        if key in mapping:
            return [mapping[key]]
        else:
            logger.warning("Unknown platform '%s'. Running all.", platform)
            return all_scrapers

    if quick:
        logger.info("Quick mode — LinkedIn skipped")
        return quick_scrapers

    return all_scrapers


def _process_and_save(raw_jobs: list[dict], source_name: str) -> tuple[int, int]:
    """Score, deduplicate, write. Returns (qualifying_count, written_count)."""
    if not raw_jobs:
        return 0, 0

    for job in raw_jobs:
        job["score"]            = score_job(job)
        job["key_requirements"] = extract_key_requirements(job.get("description", ""))

    qualifying = [j for j in raw_jobs if j["score"] >= MIN_SCORE]
    logger.info("%s | qualifying: %d/%d", source_name, len(qualifying), len(raw_jobs))

    new_jobs = filter_new(qualifying)
    logger.info("%s | new after dedup: %d", source_name, len(new_jobs))

    written = append_jobs(new_jobs)
    logger.info("%s | written to Excel: %d ✓", source_name, written)

    return len(qualifying), written


def _open_excel() -> None:
    """Open job_tracker.xlsx in the default application (Excel on Windows)."""
    if not os.path.exists(EXCEL_FILE):
        return
    try:
        if sys.platform == "win32":
            os.startfile(EXCEL_FILE)
        elif sys.platform == "darwin":
            subprocess.run(["open", EXCEL_FILE], check=False)
        else:
            subprocess.run(["xdg-open", EXCEL_FILE], check=False)
        logger.info("Opened job_tracker.xlsx")
    except Exception as exc:
        logger.debug("Could not auto-open Excel: %s", exc)


def run(platform: str | None = None, quick: bool = False, no_open: bool = False) -> dict:
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("Job Scraper started at %s", start_time.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    scrapers      = _get_scrapers(platform, quick)
    total_raw     = 0
    total_written = 0

    for name, scraper_fn in scrapers:
        logger.info("── Running scraper: %s ──", name)
        try:
            results = scraper_fn()
            logger.info("%s returned %d raw listings", name, len(results))
            total_raw += len(results)
            _, written = _process_and_save(results, name)
            total_written += written
        except KeyboardInterrupt:
            logger.warning("Interrupted during %s — data already saved up to this point", name)
            break
        except Exception as exc:
            logger.error("Scraper '%s' crashed: %s", name, exc, exc_info=True)

    elapsed = (datetime.now() - start_time).seconds

    logger.info("=" * 60)
    logger.info("SCRAPE COMPLETE — %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    logger.info("Total raw: %d | Written: %d | Elapsed: %ds",
                total_raw, total_written, elapsed)
    logger.info("=" * 60)

    # Desktop notification
    notify(
        title=NOTIFICATION_TITLE,
        message=f"New jobs: {total_written}  |  Scanned: {total_raw}  |  Time: {elapsed}s",
        duration=NOTIFICATION_TIMEOUT,
    )

    # Auto-open Excel to show results
    if not no_open and total_written > 0:
        _open_excel()

    return {"raw": total_raw, "written": total_written, "elapsed_s": elapsed}


if __name__ == "__main__":
    _setup_logging()

    parser = argparse.ArgumentParser(description="Job scraper for AI/ML roles")
    parser.add_argument("--platform", type=str, default=None,
                        help="Run only one platform: linkedin | wuzzuf | bayt | remote abroad")
    parser.add_argument("--quick", action="store_true",
                        help="Skip LinkedIn (recommended for daily use)")
    parser.add_argument("--no-open", action="store_true",
                        help="Do not auto-open Excel when done")
    args = parser.parse_args()

    run(platform=args.platform, quick=args.quick, no_open=args.no_open)
