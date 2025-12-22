import sys
import os
from pathlib import Path
import pandas as pd
import json
import hashlib

# Import constants for cleaner code
from app.constants import (
    SOURCE_MANUAL, SOURCE_MANUAL_SIMPLE,
    SEARCH_TERM_MANUAL, SEARCH_TERM_MANUAL_SIMPLE,
    SEARCH_CITY_MANUAL, SEARCH_CITY_MANUAL_SIMPLE
)

# Add JDScraper to python path
PROJECT_ROOT = Path(__file__).resolve().parents[4]
JD_SCRAPER_DIR = PROJECT_ROOT / "JDScraper"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

if str(JD_SCRAPER_DIR) not in sys.path:
    sys.path.append(str(JD_SCRAPER_DIR))

# Import from JDScraper
try:
    from JDScraper.screener import (
        run_combined_visa_senior_screener,
        run_match_screener,
        extract_structured_jd_info,
        extract_jd_metadata,
        extract_manual_full_info
    )
    from JDScraper.scan_daily import parse_match_result, parse_match_output_to_dict
except ImportError as e:
    print(f"[ERROR] Failed to import from JDScraper: {e}")
    raise

def generate_job_id(company: str, title: str, url: str) -> str:
    """Generate a unique job ID matching repository logic"""
    combined = f"{company}|{title}|{url}"
    return hashlib.md5(combined.encode()).hexdigest()[:12]

def process_manual_job(data: dict):
    """
    Process a manually added job (Advanced Mode - explicit fields):
    """
    description = data.get("description", "")
    if not description:
        raise ValueError("Description is required")

    visa_status, visa_reason, senior_status, senior_reason = run_combined_visa_senior_screener(description)
    
    warnings = []
    if visa_status != "ACCEPT":
        warnings.append(f"Visa Check Failed: {visa_reason}")
    if senior_status == "SENIOR":
        warnings.append(f"Senior Check Failed: {senior_reason}")

    match_output = run_match_screener(description)
    is_pass, overall_rating = parse_match_result(match_output)
    
    jd_info = extract_structured_jd_info(description)

    row_data = {
        "TITLE": data.get("title", "Manual Entry"),
        "COMPANY": data.get("company", "Unknown"),
        "LOCATION": data.get("location", "Unknown"),
        "JOB_URL": data.get("url", ""),
        "SOURCE": SOURCE_MANUAL,
        "IS_REMOTE": data.get("is_remote", False),
        "SEARCH_TERM": SEARCH_TERM_MANUAL,
        "SEARCH_CITY": SEARCH_CITY_MANUAL
        # DESCRIPTION removed
    }

    row_data["TECHNICAL_STACK"] = jd_info["technical_stack"]
    row_data["KEY_RESPONSIBILITIES"] = jd_info["key_responsibilities"]
    row_data["REQUIRED_EXPERIENCE"] = jd_info["required_experience"]
    row_data["SUCCESS_METRICS"] = jd_info["success_metrics"]
    row_data["SALARY_RANGE"] = jd_info["salary_range"]
    row_data["SALARY_IS_ESTIMATED"] = jd_info["salary_is_estimated"]

    match_data = parse_match_output_to_dict(match_output)
    row_data.update(match_data)

    final_visa_note = visa_reason.replace("\n", " ").replace("\r", "")
    if warnings:
        warning_str = " | ".join(warnings)
        final_visa_note = f"[MANUAL OVERRIDE: {warning_str}] " + final_visa_note
    
    row_data["VISA_ANALYSIS"] = final_visa_note

    data_dir = PROJECT_ROOT / "data"
    daily_dir = data_dir / "daily"
    good_jobs_path = daily_dir / "good_jobs.csv"
    
    single_df = pd.DataFrame([row_data])

    if good_jobs_path.exists():
        try:
            existing_df = pd.read_csv(good_jobs_path, nrows=0)
            existing_cols = existing_df.columns.tolist()
            for col in existing_cols:
                if col not in single_df.columns:
                    single_df[col] = "N/A"
            single_df = single_df[existing_cols]
        except Exception as e:
            print(f"[WARN] Failed to read existing CSV header: {e}")
            pass
    
    header = not good_jobs_path.exists()
    single_df.to_csv(good_jobs_path, mode='a', header=header, index=False)

    master_path = data_dir / "jobs_master.csv"
    if master_path.exists():
        try:
            master_row = {
                "TITLE": row_data["TITLE"],
                "COMPANY": row_data["COMPANY"],
                "LOCATION": row_data["LOCATION"],
                "JOB_URL": row_data["JOB_URL"],
                "SOURCE": SOURCE_MANUAL,
                "IS_REMOTE": row_data["IS_REMOTE"],
                "SEARCH_TERM": SEARCH_TERM_MANUAL,
                "SEARCH_CITY": SEARCH_CITY_MANUAL
            }
            master_df = pd.DataFrame([master_row])
            master_df.to_csv(master_path, mode='a', header=False, index=False)
        except Exception as e:
            print(f"[WARN] Failed to update master csv: {e}")

    # Generate Correct ID
    job_id = generate_job_id(row_data['COMPANY'], row_data['TITLE'], row_data['JOB_URL'])
    
    return {
        "status": "success",
        "warnings": warnings,
        "match_rating": overall_rating,
        "job_id": job_id
    }

def process_manual_job_simple(raw_jd_text: str):
    """
    Process a manually added job from raw JD text (Optimized):
    """
    if not raw_jd_text or not raw_jd_text.strip():
        raise ValueError("Raw JD text is required")

    print("[INFO] Running Unified Extraction on raw JD text...")
    extracted_data = extract_manual_full_info(raw_jd_text)

    title = extracted_data.get("job_title", "Unknown Role")
    company = extracted_data.get("company", "Unknown Company")
    location = extracted_data.get("location", "Unknown")
    is_remote = extracted_data.get("is_remote", False)
    url = extracted_data.get("job_url", "")
    description = extracted_data.get("description", raw_jd_text)

    print(f"[INFO] Extracted: {title} at {company} ({location})")

    visa_status, visa_reason, senior_status, senior_reason = run_combined_visa_senior_screener(description)

    warnings = []
    if visa_status != "ACCEPT":
        warnings.append(f"Visa Check Failed: {visa_reason}")
    if senior_status == "SENIOR":
        warnings.append(f"Senior Check Failed: {senior_reason}")

    match_output = run_match_screener(description)
    is_pass, overall_rating = parse_match_result(match_output)

    row_data = {
        "TITLE": title,
        "COMPANY": company,
        "LOCATION": location,
        "JOB_URL": url,
        "SOURCE": SOURCE_MANUAL_SIMPLE,
        "IS_REMOTE": is_remote,
        "SEARCH_TERM": SEARCH_TERM_MANUAL_SIMPLE,
        "SEARCH_CITY": SEARCH_CITY_MANUAL_SIMPLE
    }

    def to_str(val):
        if isinstance(val, list):
            return " | ".join(str(x) for x in val)
        return str(val) if val is not None else "N/A"

    row_data["TECHNICAL_STACK"] = to_str(extracted_data.get("technical_stack", "N/A"))
    row_data["KEY_RESPONSIBILITIES"] = to_str(extracted_data.get("key_responsibilities", "N/A"))
    row_data["REQUIRED_EXPERIENCE"] = to_str(extracted_data.get("required_experience", "N/A"))
    row_data["SUCCESS_METRICS"] = to_str(extracted_data.get("success_metrics", "N/A"))
    row_data["SALARY_RANGE"] = to_str(extracted_data.get("salary_range", "N/A"))
    row_data["SALARY_IS_ESTIMATED"] = extracted_data.get("salary_is_estimated", True)

    match_data = parse_match_output_to_dict(match_output)
    row_data.update(match_data)

    final_visa_note = visa_reason.replace("\n", " ").replace("\r", "")
    if warnings:
        warning_str = " | ".join(warnings)
        final_visa_note = f"[MANUAL OVERRIDE: {warning_str}] " + final_visa_note

    row_data["VISA_ANALYSIS"] = final_visa_note

    data_dir = PROJECT_ROOT / "data"
    daily_dir = data_dir / "daily"
    good_jobs_path = daily_dir / "good_jobs.csv"

    single_df = pd.DataFrame([row_data])

    if good_jobs_path.exists():
        try:
            existing_df = pd.read_csv(good_jobs_path, nrows=0)
            existing_cols = existing_df.columns.tolist()
            for col in existing_cols:
                if col not in single_df.columns:
                    single_df[col] = "N/A"
            single_df = single_df[existing_cols]
        except Exception as e:
            print(f"[WARN] Failed to read existing CSV header: {e}")
            pass

    header = not good_jobs_path.exists()
    single_df.to_csv(good_jobs_path, mode='a', header=header, index=False)

    master_path = data_dir / "jobs_master.csv"
    if master_path.exists():
        try:
            master_row = {
                "TITLE": row_data["TITLE"],
                "COMPANY": row_data["COMPANY"],
                "LOCATION": row_data["LOCATION"],
                "JOB_URL": row_data["JOB_URL"],
                "SOURCE": SOURCE_MANUAL_SIMPLE,
                "IS_REMOTE": row_data["IS_REMOTE"],
                "SEARCH_TERM": SEARCH_TERM_MANUAL_SIMPLE,
                "SEARCH_CITY": SEARCH_CITY_MANUAL_SIMPLE
            }
            master_df = pd.DataFrame([master_row])
            master_df.to_csv(master_path, mode='a', header=False, index=False)
        except Exception as e:
            print(f"[WARN] Failed to update master csv: {e}")

    # Generate Correct ID
    job_id = generate_job_id(row_data['COMPANY'], row_data['TITLE'], row_data['JOB_URL'])

    return {
        "status": "success",
        "warnings": warnings,
        "match_rating": overall_rating,
        "extracted_metadata": extracted_data,
        "job_id": job_id
    }
