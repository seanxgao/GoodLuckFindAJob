import os
import csv
import json
import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd
from jobspy import scrape_jobs

# ================== Configuration ==================

# ScraperAPI key from environment variable
API_KEY = os.getenv("SCRAPERAPI_KEY")
if not API_KEY:
    raise ValueError(
        "SCRAPERAPI_KEY environment variable not set. "
        "Please set it using: export SCRAPERAPI_KEY='your-key-here' (bash) "
        "or $env:SCRAPERAPI_KEY = 'your-key-here' (PowerShell)"
    )

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"

DATA_DIR = PROJECT_ROOT / "data"
DAILY_DIR = DATA_DIR / "daily"
MASTER_PATH = DATA_DIR / "jobs_master.csv"

# Load search configuration from config file
with open(CONFIG_DIR / "search.json", "r", encoding="utf-8") as f:
    SEARCH_CONFIG = json.load(f)

# Extract configuration values
LOCATIONS = SEARCH_CONFIG["locations"]["cities"]
REMOTE_LOCATIONS = SEARCH_CONFIG["locations"]["remote"]
ALL_LOCATIONS = LOCATIONS + REMOTE_LOCATIONS
SEARCH_TERMS = SEARCH_CONFIG["search_terms"]
RESULTS_WANTED = SEARCH_CONFIG["scraper"]["results_per_city"]
SITE_NAME = SEARCH_CONFIG["scraper"]["site_name"]
DESCRIPTION_FORMAT = SEARCH_CONFIG["scraper"]["description_format"]
VERBOSE = SEARCH_CONFIG["scraper"]["verbose"]

# ================== Utility Functions ==================


def get_proxy_url() -> str:
    if not API_KEY:
        raise RuntimeError("SCRAPERAPI_KEY not set in env or code.")
    return (
        "http://api.scraperapi.com"
        f"?api_key={API_KEY}"
        "&country=us"
        "&keep_headers=true"
        "&url={{url}}"
    )


def fetch_jobs_multi_city(days: int = 1) -> pd.DataFrame:
    """
    Fetch job postings for multiple cities (including Remote) and return deduplicated DataFrame.

    Args:
        days: Search for jobs within the specified number of days (default: 1, searches within 24 hours)
    """
    proxy_url = get_proxy_url()
    all_jobs = []
    hours_old = 24 * days

    for city in ALL_LOCATIONS:
        for term in SEARCH_TERMS:
            print(f"\n[*] Fetching jobs for: {term} in {city} (within {days} day(s), {hours_old} hours)")
            try:
                df = scrape_jobs(
                    site_name=SITE_NAME,
                    search_term=term,
                    location=city,
                    results_wanted=RESULTS_WANTED,
                    hours_old=hours_old,
                    description_format=DESCRIPTION_FORMAT,
                    proxy=proxy_url,
                    verbose=VERBOSE,
                )
            except Exception as e:
                print(f"[!] Error fetching {city} / {term}: {e}")
                continue

            if df is None or len(df) == 0:
                print(f"    [-] No jobs fetched for {city} / {term}")
                continue

            df["SEARCH_CITY"] = city
            df["SEARCH_TERM"] = term
            all_jobs.append(df)

    if not all_jobs:
        print("[!] No jobs found for ANY location.")
        return pd.DataFrame()

    df_all = pd.concat(all_jobs, ignore_index=True)

    # Normalize column names to uppercase to prevent filtering issues
    df_all.columns = [str(c).upper() for c in df_all.columns]

    # Map site -> SOURCE (if exists)
    if "SITE" in df_all.columns:
        df_all.rename(columns={"SITE": "SOURCE"}, inplace=True)

    # Keep only the required columns (filter conditionally in case some don't exist)
    keep_cols = [
        "TITLE",
        "COMPANY",
        "LOCATION",
        "SEARCH_CITY",
        "SEARCH_TERM",
        "JOB_URL",
        "DESCRIPTION",
        "SOURCE",
        "IS_REMOTE",
    ]
    df_all = df_all[[c for c in keep_cols if c in df_all.columns]]

    # Clean and normalize URLs
    if "JOB_URL" in df_all.columns:
        df_all["JOB_URL"] = df_all["JOB_URL"].astype(str).str.strip()

    # Clean newlines from all text columns to ensure CSV format is one record per line
    str_cols = df_all.select_dtypes(include=['object']).columns
    for col in str_cols:
        # Replace newlines with spaces to avoid breaking CSV structure
        df_all[col] = df_all[col].astype(str).str.replace(r'[\r\n]+', ' ', regex=True)

    # Remove records with empty URLs (most jobs should have a URL)
    if "JOB_URL" in df_all.columns:
        df_all = df_all[df_all["JOB_URL"].str.len() > 0]

    # Deduplicate by URL within current batch
    if "JOB_URL" in df_all.columns:
        df_all = df_all.drop_duplicates(subset=["JOB_URL"])

    print(
        f"[+] Total unique jobs fetched across {len(ALL_LOCATIONS)} locations: {len(df_all)}"
    )
    return df_all


def load_master() -> pd.DataFrame:
    if not MASTER_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(MASTER_PATH)


def save_master(df: pd.DataFrame):
    # Drop DESCRIPTION column to save space (full JD stored in good_jobs.csv only)
    df_to_save = df.copy()
    if "DESCRIPTION" in df_to_save.columns:
        df_to_save = df_to_save.drop(columns=["DESCRIPTION"])

    df_to_save.to_csv(
        MASTER_PATH,
        index=False,
        quoting=csv.QUOTE_NONNUMERIC,
        encoding="utf-8",
    )


def dedupe_against_master(df_raw: pd.DataFrame, df_master: pd.DataFrame) -> pd.DataFrame:
    """
    Deduplicate current batch df_raw against historical master, returning only truly new jobs.
    Prioritizes JOB_URL for deduplication; for rare cases without URL, uses TITLE+COMPANY+LOCATION.
    """
    if df_raw.empty:
        return df_raw

    # If master has no data yet, return raw as-is
    if df_master.empty:
        return df_raw

    raw = df_raw.copy()
    master = df_master.copy()

    # Normalize string types
    for col in ["JOB_URL", "TITLE", "COMPANY", "LOCATION"]:
        if col in raw.columns:
            raw[col] = raw[col].astype(str).str.strip()
        if col in master.columns:
            master[col] = master[col].astype(str).str.strip()

    # Deduplicate by JOB_URL first
    if "JOB_URL" in raw.columns and "JOB_URL" in master.columns:
        seen_urls = set(master["JOB_URL"])
        mask_new = ~raw["JOB_URL"].isin(seen_urls)
        raw = raw[mask_new]

    # For rare records without JOB_URL, use (TITLE, COMPANY, LOCATION) as fallback
    if "JOB_URL" in raw.columns:
        # Look only at records with empty/missing JOB_URL
        mask_no_url = raw["JOB_URL"].isna() | (raw["JOB_URL"].str.len() == 0)
        raw_no_url = raw[mask_no_url]
        raw_has_url = raw[~mask_no_url]

        if not raw_no_url.empty and all(
            col in raw_no_url.columns for col in ["TITLE", "COMPANY", "LOCATION"]
        ):
            if all(col in master.columns for col in ["TITLE", "COMPANY", "LOCATION"]):
                master_keys = set(
                    zip(master["TITLE"], master["COMPANY"], master["LOCATION"])
                )
                mask_new_no_url = [
                    (t, c, l) not in master_keys
                    for t, c, l in zip(
                        raw_no_url["TITLE"],
                        raw_no_url["COMPANY"],
                        raw_no_url["LOCATION"],
                    )
                ]
                raw_no_url = raw_no_url[mask_new_no_url]

        raw = pd.concat([raw_has_url, raw_no_url], ignore_index=True)

    return raw


# ================== Main Process ==================


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Fetch and update job listings')
    parser.add_argument(
        'days',
        type=int,
        nargs='?',
        default=1,
        help='Search for jobs within the specified number of days (default: 1, searches within 24*1 hours)'
    )
    args = parser.parse_args()

    # Ensure data directories exist
    DATA_DIR.mkdir(exist_ok=True)
    DAILY_DIR.mkdir(parents=True, exist_ok=True)

    df_raw = fetch_jobs_multi_city(days=args.days)
    if df_raw.empty:
        print("[*] Nothing fetched, exiting.")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    daily_path = DAILY_DIR / f"jobs_{today_str}.csv"

    if not MASTER_PATH.exists():
        # First run: treat all fetched jobs as new
        print("[*] Master not found, treating ALL fetched jobs as NEW.")
        df_new = df_raw.copy()
        df_new.to_csv(
            daily_path,
            index=False,
            quoting=csv.QUOTE_NONNUMERIC,
            encoding="utf-8",
        )
        save_master(df_new)
        print(f"[+] Saved {len(df_new)} new jobs to {daily_path}")
        print(f"[+] Initialized master with {len(df_new)} jobs.")
        return

    # Subsequent runs: deduplicate against master, keep only truly new jobs
    df_master = load_master()
    df_new = dedupe_against_master(df_raw, df_master)

    if df_new.empty:
        print("[*] No truly NEW jobs found today (all already in master).")
        return

    # Save today's new jobs
    df_new.to_csv(
        daily_path,
        index=False,
        quoting=csv.QUOTE_NONNUMERIC,
        encoding="utf-8",
    )
    print(f"[+] Saved {len(df_new)} NEW jobs to {daily_path}")

    # Update master and do one more URL deduplication for safety
    # We drop DESCRIPTION from the new records BEFORE concatenating to avoid
    # blowing up memory by adding a DESCRIPTION column to the entire master dataframe
    df_new_for_master = df_new.copy()
    if "DESCRIPTION" in df_new_for_master.columns:
        df_new_for_master = df_new_for_master.drop(columns=["DESCRIPTION"])
        
    df_all = pd.concat([df_master, df_new_for_master], ignore_index=True)

    if "JOB_URL" in df_all.columns:
        df_all["JOB_URL"] = df_all["JOB_URL"].astype(str).str.strip()
        df_all = df_all[df_all["JOB_URL"].str.len() > 0]
        df_all = df_all.drop_duplicates(subset=["JOB_URL"])

    save_master(df_all)
    print(f"[+] Updated master to {len(df_all)} total unique jobs.")


if __name__ == "__main__":
    main()
