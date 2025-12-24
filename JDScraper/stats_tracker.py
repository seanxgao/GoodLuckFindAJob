"""
Job scraping statistics tracker.
Tracks fetch history, screening results, and application counts.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import pandas as pd

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
STATS_FILE = DATA_DIR / "scrape_stats.json"
GOOD_JOBS_CSV = DATA_DIR / "daily" / "good_jobs.csv"


def load_stats() -> Dict[str, Any]:
    """Load statistics from file, or return default structure if not exists."""
    if STATS_FILE.exists():
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load stats file: {e}")

    # Default structure
    return {
        "last_fetch_time": None,
        "total_fetched": 0,
        "total_passed_screening": 0,
        "total_visa_blocked": 0,
        "total_senior_blocked": 0,
        "total_match_failed": 0,
        "history": []
    }


def save_stats(stats: Dict[str, Any]):
    """Save statistics to file."""
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Could not save stats file: {e}")


def update_fetch_stats(jobs_fetched: int):
    """
    Update statistics after fetching jobs.

    Args:
        jobs_fetched: Number of new jobs fetched in this run
    """
    stats = load_stats()

    # Update timestamp
    now = datetime.now().isoformat()
    stats["last_fetch_time"] = now

    # Update totals
    stats["total_fetched"] += jobs_fetched

    # Add to history
    stats["history"].append({
        "timestamp": now,
        "type": "fetch",
        "jobs_fetched": jobs_fetched
    })

    save_stats(stats)
    print(f"[Stats] Updated: {jobs_fetched} jobs fetched. Total fetched: {stats['total_fetched']}")


def update_screening_stats(visa_blocked: int = 0, senior_blocked: int = 0, match_failed: int = 0, passed: int = 0):
    """
    Update statistics after screening jobs.

    Args:
        visa_blocked: Number of jobs blocked by visa requirements
        senior_blocked: Number of jobs blocked for being senior-level
        match_failed: Number of jobs that failed match screening
        passed: Number of jobs that passed all screening
    """
    stats = load_stats()

    # Update totals
    stats["total_visa_blocked"] += visa_blocked
    stats["total_senior_blocked"] += senior_blocked
    stats["total_match_failed"] += match_failed
    stats["total_passed_screening"] += passed

    # Add to history
    if any([visa_blocked, senior_blocked, match_failed, passed]):
        stats["history"].append({
            "timestamp": datetime.now().isoformat(),
            "type": "screening",
            "visa_blocked": visa_blocked,
            "senior_blocked": senior_blocked,
            "match_failed": match_failed,
            "passed": passed
        })

    save_stats(stats)


def get_applied_count() -> int:
    """
    Count number of jobs with 'applied' status from good_jobs tracking.
    This requires checking the offerClick backend data.
    """
    try:
        # Check if there's a statuses file in offerClick data
        statuses_file = PROJECT_ROOT / "offerClick" / "backend" / "data" / "statuses.json"
        if statuses_file.exists():
            with open(statuses_file, "r", encoding="utf-8") as f:
                statuses = json.load(f)
                # Count jobs with 'applied' status
                applied_count = sum(1 for status in statuses.values() if status == "applied")
                return applied_count
    except Exception as e:
        print(f"Warning: Could not count applied jobs: {e}")

    return 0


def print_stats_summary():
    """Print a summary of all statistics."""
    stats = load_stats()
    applied_count = get_applied_count()

    print("\n" + "="*60)
    print("JOB SCRAPING STATISTICS SUMMARY")
    print("="*60)

    if stats["last_fetch_time"]:
        print(f"Last Fetch: {stats['last_fetch_time']}")
    else:
        print("Last Fetch: Never")

    print(f"\nTotal Jobs Fetched: {stats['total_fetched']}")
    print(f"Total Passed Screening: {stats['total_passed_screening']}")
    print(f"Total Visa Blocked: {stats['total_visa_blocked']}")
    print(f"Total Senior Blocked: {stats['total_senior_blocked']}")
    print(f"Total Match Failed: {stats['total_match_failed']}")
    print(f"\nJobs Applied To: {applied_count}")

    # Calculate pass rate if we have data
    total_screened = stats['total_visa_blocked'] + stats['total_senior_blocked'] + stats['total_match_failed'] + stats['total_passed_screening']
    if total_screened > 0:
        pass_rate = (stats['total_passed_screening'] / total_screened) * 100
        print(f"\nScreening Pass Rate: {pass_rate:.1f}%")

    print("="*60 + "\n")


def get_days_since_last_fetch(max_days: int = 14) -> Optional[int]:
    """
    Calculate number of days since last fetch, rounded up to 24-hour periods.
    Caps at max_days to avoid fetching too far back (e.g., on first run or after long break).

    Args:
        max_days: Maximum number of days to search back (default: 14)

    Returns:
        Number of days, capped at max_days, or None if never fetched before
    """
    stats = load_stats()

    if not stats["last_fetch_time"]:
        return None

    try:
        last_fetch = datetime.fromisoformat(stats["last_fetch_time"])
        now = datetime.now()

        # Calculate hours difference
        hours_diff = (now - last_fetch).total_seconds() / 3600

        # Round up to nearest 24-hour period
        import math
        days = math.ceil(hours_diff / 24)

        # Cap at max_days and ensure minimum of 1
        days = max(1, min(days, max_days))

        return days
    except Exception as e:
        print(f"Warning: Could not calculate days since last fetch: {e}")
        return None


if __name__ == "__main__":
    # When run directly, print stats summary
    print_stats_summary()
