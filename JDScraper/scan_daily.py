import os
import sys
import json
import pandas as pd
from pathlib import Path
from screener import quick_senior_keyword_check, quick_visa_keyword_check, run_combined_visa_senior_screener, run_match_screener, extract_structured_jd_info
from stats_tracker import update_screening_stats, print_stats_summary

# Load screening configuration
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"

with open(CONFIG_DIR / "screening.json", "r", encoding="utf-8") as f:
    SCREENING_CONFIG = json.load(f)

MATCH_THRESHOLD = SCREENING_CONFIG["match_threshold"]

def parse_match_output_to_dict(text):
    data = {
        "SYSTEMS_FIT": "UNKNOWN",
        "RETRIEVAL_INFRA_FIT": "UNKNOWN",
        "ALGORITHMIC_ML_FIT": "UNKNOWN",
        "OVERALL_MATCH": "UNKNOWN",
        "MATCH_REASON": ""
    }
    if not text:
        return data

    lines = text.splitlines()
    reason_lines = []
    in_reason = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("Systems_Fit:"):
            data["SYSTEMS_FIT"] = line.split(":", 1)[1].strip()
        elif line.startswith("Retrieval_Infra_Fit:"):
            data["RETRIEVAL_INFRA_FIT"] = line.split(":", 1)[1].strip()
        elif line.startswith("Algorithmic_ML_Fit:"):
            data["ALGORITHMIC_ML_FIT"] = line.split(":", 1)[1].strip()
        elif line.startswith("Overall:"):
            data["OVERALL_MATCH"] = line.split(":", 1)[1].strip()
        elif line.startswith("Reason:"):
            in_reason = True
            # Check if there is content on the same line
            parts = line.split(":", 1)
            if len(parts) > 1 and parts[1].strip():
                reason_lines.append(parts[1].strip())
        elif in_reason:
            reason_lines.append(line)

    # Join reason lines with a pipe separator for single-line CSV cleanliness
    data["MATCH_REASON"] = " | ".join(reason_lines)
    return data

def parse_match_result(match_text):
    """
    Parses the text output from run_match_screener to determine if it's a pass.
    Returns (is_pass, overall_rating)
    """
    if not match_text:
        return False, "NONE"
    
    lines = match_text.splitlines()
    overall_rating = "0"
    
    for line in lines:
        if line.strip().startswith("Overall:"):
            # Extract the part after 'Overall:'
            parts = line.split(":", 1)
            if len(parts) > 1:
                overall_rating = parts[1].strip()
            break
            
    # Try to convert to float/int
    try:
        score = float(overall_rating)
        # Use configured threshold
        is_pass = score >= MATCH_THRESHOLD
        return is_pass, overall_rating
    except ValueError:
        # Fallback for old format or errors
        upper = overall_rating.upper()
        # "HIGH" (great) or "MEDIUM" (passable)
        if "HIGH" in upper or "MEDIUM" in upper or "STRONG MATCH" in upper:
            return True, overall_rating
        return False, overall_rating

def scan_jobs():
    # Setup paths
    base_dir = Path(__file__).resolve().parent
    daily_dir = base_dir.parent / "data" / "daily"
    good_jobs_path = daily_dir / "good_jobs.csv"

    # Ensure daily directory exists
    if not daily_dir.exists():
        print(f"Error: Daily directory not found at {daily_dir}")
        return

    # Get list of job files (exclude good_jobs.csv itself if it matches)
    job_files = [f for f in daily_dir.glob("jobs_*.csv") if f.name != "good_jobs.csv" and f.name != "jobs_master.csv"]

    print(f"Found {len(job_files)} daily job files to scan.")

    # Load already processed URLs from good_jobs.csv to avoid duplicates
    processed_urls = set()
    if good_jobs_path.exists():
        try:
            df_existing = pd.read_csv(good_jobs_path)
            if "JOB_URL" in df_existing.columns:
                processed_urls = set(df_existing["JOB_URL"].dropna())
        except Exception as e:
            print(f"Warning: Could not read existing good_jobs.csv: {e}")

    print(f"Already {len(processed_urls)} jobs in good_jobs.csv (will skip these).")

    # Statistics counters
    stats_visa_blocked = 0
    stats_senior_blocked = 0
    stats_match_failed = 0
    stats_passed = 0
    
    for csv_file in job_files:
        print(f"\nProcessing file: {csv_file.name}")
        try:
            df = pd.read_csv(csv_file)
        except Exception as e:
            print(f"Error reading {csv_file}: {e}")
            continue
            
        if "DESCRIPTION" not in df.columns:
            print(f"Skipping {csv_file}: Missing DESCRIPTION column.")
            continue
            
        total_rows = len(df)
        for index, row in df.iterrows():
            url = row.get("JOB_URL", "")
            title = row.get("TITLE", "Unknown Title")
            
            # Skip if we already have this job in good_jobs
            if url in processed_urls:
                continue
            
            description = row.get("DESCRIPTION", "")
            if not isinstance(description, str) or not description.strip():
                continue
                
            print(f"[{index+1}/{total_rows}] Screening: {title[:50]}...", end="", flush=True)
            
            try:
                # 0. Quick keyword checks (fast, before LLM calls)
                if quick_senior_keyword_check(title):
                    print(f" -> Quick Senior REJECT")
                    stats_senior_blocked += 1
                    continue

                if quick_visa_keyword_check(description):
                    print(f" -> Quick Visa REJECT")
                    stats_visa_blocked += 1
                    continue

                # 1. Combined Visa & Senior Screen (single API call)
                visa_result, visa_reason, senior_result, senior_reason = run_combined_visa_senior_screener(description)
                if senior_result == "SENIOR":
                    print(f" -> Senior REJECT")
                    stats_senior_blocked += 1
                    continue
                if visa_result != "ACCEPT":
                    print(f" -> Visa REJECT")
                    stats_visa_blocked += 1
                    continue

                # 3. Match Screen
                match_output = run_match_screener(description)
                is_pass, overall_rating = parse_match_result(match_output)

                if is_pass:
                    print(f" -> {overall_rating}! Added.")
                    stats_passed += 1

                    # Extract structured JD information
                    print(f"    Extracting structured info...", end="", flush=True)
                    jd_info = extract_structured_jd_info(description)
                    print(f" Done.")

                    # Prepare row data
                    row_data = row.to_dict()

                    # Keep original description (for reference/resume generation)
                    # Add structured fields
                    row_data["TECHNICAL_STACK"] = jd_info["technical_stack"]
                    row_data["KEY_RESPONSIBILITIES"] = jd_info["key_responsibilities"]
                    row_data["REQUIRED_EXPERIENCE"] = jd_info["required_experience"]
                    row_data["SUCCESS_METRICS"] = jd_info["success_metrics"]
                    row_data["SALARY_RANGE"] = jd_info["salary_range"]
                    row_data["SALARY_IS_ESTIMATED"] = jd_info["salary_is_estimated"]

                    # Parse match output into separate columns
                    match_data = parse_match_output_to_dict(match_output)
                    row_data.update(match_data)

                    # Visa reason
                    row_data["VISA_ANALYSIS"] = visa_reason.replace("\n", " ").replace("\r", "")

                    # Remove full description to save space
                    if "DESCRIPTION" in row_data:
                        del row_data["DESCRIPTION"]

                    # Convert to DataFrame
                    single_df = pd.DataFrame([row_data])

                    # Append to CSV immediately
                    header = not good_jobs_path.exists()
                    single_df.to_csv(good_jobs_path, mode='a', header=header, index=False)

                    # Mark as processed
                    processed_urls.add(url)
                else:
                    print(f" -> Match FAIL ({overall_rating})")
                    stats_match_failed += 1
            except Exception as e:
                print(f" -> Error during screening: {e}")
                continue

    print("\nDone scanning all files.")

    # Update statistics
    if any([stats_visa_blocked, stats_senior_blocked, stats_match_failed, stats_passed]):
        print(f"\nScreening Results:")
        print(f"  Visa Blocked: {stats_visa_blocked}")
        print(f"  Senior Blocked: {stats_senior_blocked}")
        print(f"  Match Failed: {stats_match_failed}")
        print(f"  Passed: {stats_passed}")

        update_screening_stats(
            visa_blocked=stats_visa_blocked,
            senior_blocked=stats_senior_blocked,
            match_failed=stats_match_failed,
            passed=stats_passed
        )
        print_stats_summary()

if __name__ == "__main__":
    scan_jobs()
