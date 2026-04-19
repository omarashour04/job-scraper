"""
main.py — Orchestrates the full job search pipeline.

Pipeline:
  1. Run scrapers (LinkedIn skipped in --quick mode — it blocks aggressively)
  2. Score every listing
  3. Deduplicate against seen_jobs.json
  4. Append qualifying listings to job_tracker.xlsx
  5. Send desktop notification

Usage:
    python main.py              — full run including LinkedIn
    python main.py --quick      — Wuzzuf + Bayt + Remote APIs (no LinkedIn)
    python main.py --platform wuzzuf
    python main.py --platform bayt
    python main.py --platform linkedin
    python main.py --platform "remote abroad"
"""

import argparse
import logging
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import LOG_FILE, MIN_SCORE, NOTIFICATION_TITLE, NOTIFICATION_TIMEOUT
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

    # --quick skips LinkedIn entirely — it blocks the guest API aggressively
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


def run(platform: str | None = None, quick: bool = False) -> dict:
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("Job Scraper started at %s", start_time.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    # ── Step 1: Scrape ────────────────────────────────────────────────────────
    scrapers   = _get_scrapers(platform, quick)
    raw_jobs: list[dict] = []

    for name, scraper_fn in scrapers:
        logger.info("── Running scraper: %s ──", name)
        try:
            results = scraper_fn()
            logger.info("%s returned %d raw listings", name, len(results))
            raw_jobs.extend(results)
        except Exception as exc:
            logger.error("Scraper '%s' crashed: %s", name, exc, exc_info=True)

    logger.info("Total raw listings: %d", len(raw_jobs))

    # ── Step 2: Score ─────────────────────────────────────────────────────────
    for job in raw_jobs:
        job["score"]            = score_job(job)
        job["key_requirements"] = extract_key_requirements(job.get("description", ""))

    qualifying = [j for j in raw_jobs if j["score"] >= MIN_SCORE]
    logger.info("After scoring (≥%d): %d listings qualify", MIN_SCORE, len(qualifying))

    # ── Step 3: Deduplicate ───────────────────────────────────────────────────
    new_jobs = filter_new(qualifying)
    logger.info("After deduplication: %d new listings", len(new_jobs))

    # ── Step 4: Write to Excel ────────────────────────────────────────────────
    written = append_jobs(new_jobs)

    # ── Step 5: Summary & notification ───────────────────────────────────────
    high   = sum(1 for j in new_jobs if priority_label(j["score"]) == "High")
    medium = sum(1 for j in new_jobs if priority_label(j["score"]) == "Medium")
    low    = sum(1 for j in new_jobs if priority_label(j["score"]) == "Low")

    elapsed = (datetime.now() - start_time).seconds
    summary = {
        "raw": len(raw_jobs), "qualifying": len(qualifying),
        "new": len(new_jobs), "written": written,
        "high": high, "medium": medium, "low": low,
        "elapsed_s": elapsed,
    }

    top_jobs = sorted(new_jobs, key=lambda j: j["score"], reverse=True)[:5]

    logger.info("=" * 60)
    logger.info("SCRAPE COMPLETE — %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    logger.info("Raw: %d | Qualifying: %d | New: %d | Written: %d",
                summary["raw"], summary["qualifying"], summary["new"], summary["written"])
    logger.info("Priority — High: %d | Medium: %d | Low: %d", high, medium, low)
    logger.info("Elapsed: %ds", elapsed)
    if top_jobs:
        logger.info("── Top picks ──")
        for i, j in enumerate(top_jobs, 1):
            logger.info("  %d. [%d] %s @ %s  %s",
                        i, j["score"], j["title"], j["company"], j.get("url", ""))
    logger.info("=" * 60)

    notif_lines = [
        f"New jobs: {written}   (High: {high} | Med: {medium} | Low: {low})",
        f"Total scanned: {summary['raw']}   Run time: {elapsed}s",
    ]
    if top_jobs:
        best = top_jobs[0]
        notif_lines.append(f"Best: {best['title']} @ {best['company']} [{best['score']}/10]")

    notify(title=NOTIFICATION_TITLE, message="\n".join(notif_lines), duration=NOTIFICATION_TIMEOUT)
    return summary


if __name__ == "__main__":
    _setup_logging()

    parser = argparse.ArgumentParser(description="Job scraper for AI/ML roles")
    parser.add_argument("--platform", type=str, default=None,
                        help="Run only one platform: linkedin | wuzzuf | bayt | remote abroad")
    parser.add_argument("--quick", action="store_true",
                        help="Skip LinkedIn (faster, avoids rate-limit bans). Recommended for daily runs.")
    args = parser.parse_args()

    run(platform=args.platform, quick=args.quick)
