"""
deduplicator.py — Persistent URL-based deduplication across scraper runs.

Uses a local JSON file (seen_jobs.json) to remember which job URLs have
already been written to the Excel file. This prevents the same listing
from appearing twice across separate invocations of the scraper.
"""

import json
import os
import logging

from config import SEEN_FILE

logger = logging.getLogger(__name__)


def _load() -> set[str]:
    """Load the set of seen URLs from disk."""
    if not os.path.exists(SEEN_FILE):
        return set()
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data)
    except (json.JSONDecodeError, IOError) as exc:
        logger.warning("Could not load seen_jobs.json: %s — starting fresh", exc)
        return set()


def _save(seen: set[str]) -> None:
    """Persist the seen URL set to disk."""
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(seen), f, indent=2)
    except IOError as exc:
        logger.error("Could not save seen_jobs.json: %s", exc)


def filter_new(jobs: list[dict]) -> list[dict]:
    """
    Given a list of job dicts (each with a 'url' key), return only those
    whose URL has NOT been seen in a previous run.

    Side effect: updates and saves the seen-URL store with all new URLs.
    """
    seen = _load()
    new_jobs = []

    for job in jobs:
        url = job.get("url", "").strip()
        if not url:
            # No URL — cannot deduplicate, include it anyway
            new_jobs.append(job)
            continue
        if url not in seen:
            new_jobs.append(job)
            seen.add(url)

    _save(seen)
    logger.info("Deduplicator | input=%d  new=%d  already_seen=%d",
                len(jobs), len(new_jobs), len(jobs) - len(new_jobs))
    return new_jobs
