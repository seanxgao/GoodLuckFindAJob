import os
import json
from pathlib import Path
from openai import OpenAI

# OpenAI API Key from environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY environment variable not set. "
        "Please set it using: $env:OPENAI_API_KEY = 'your-key-here' (PowerShell) "
        "or export OPENAI_API_KEY='your-key-here' (bash)"
    )

client = OpenAI(api_key=OPENAI_API_KEY)

# ================== CONFIGURATION ===================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
PROMPTS_DIR = CONFIG_DIR / "prompts" / "scraper"

# Load screening configuration
with open(CONFIG_DIR / "screening.json", "r", encoding="utf-8") as f:
    SCREENING_CONFIG = json.load(f)

# Extract configuration values
SCREENING_MODEL = SCREENING_CONFIG["models"]["screening"]
SCREENING_TEMP = SCREENING_CONFIG["temperatures"]["screening"]
MAX_DESC_LENGTH = SCREENING_CONFIG["max_description_length"]

# ================== PROMPTS ===================

def load_prompt(filename: str) -> str:
    """Load a prompt from the prompts directory"""
    prompt_path = PROMPTS_DIR / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")

# Load prompts from files
MATCH_PROMPT = load_prompt("match_screening.txt")
COMBINED_VISA_SENIOR_PROMPT = load_prompt("combined_visa_senior.txt")
STRUCTURED_EXTRACTION_PROMPT = load_prompt("jd_structured_extraction.txt")
METADATA_EXTRACTION_PROMPT = load_prompt("jd_metadata_extraction.txt")
MANUAL_FULL_EXTRACTION_PROMPT = load_prompt("jd_extraction_manual.txt")

def quick_senior_keyword_check(title: str) -> bool:
    """
    Quick keyword-based check for obvious senior positions.
    Returns True if should be rejected (is senior), False otherwise.
    """
    if not title:
        return False

    text = f"{title}".lower()

    # Keywords that indicate senior positions (in title)
    senior_keywords = [
        "senior", "sr.", "sr ", "lead", "principal",
        "chief", "director", "head of", "vp ", "vice president",
        "manager"
    ]

    # Check if any keyword appears (case-insensitive)
    for keyword in senior_keywords:
        if keyword in text:
            return True

    return False

def quick_visa_keyword_check(description: str) -> bool:
    """
    Quick keyword-based check for obvious visa blockers.
    Returns True if should be rejected (has citizenship/clearance requirements), False otherwise.
    """
    if not description:
        return False

    text = description.lower()

    # Keywords that indicate citizenship/clearance requirements
    # These are strong signals that the job is not visa-friendly
    visa_blocker_keywords = [
        "us citizen only",
        "u.s. citizen only",
        "us citizenship required",
        "u.s. citizenship required",
        "must be a us citizen",
        "must be a u.s. citizen",
        "citizen of the united states",
        "citizenship is required",
        "green card only",
        "permanent resident only",
        "green card required",
        "cannot sponsor",
        "will not sponsor",
        "no visa sponsorship",
        "not eligible for visa sponsorship",
        "security clearance required",
        "secret clearance required",
        "top secret clearance",
        "ts/sci required",
        "ts clearance required",
        "sci clearance required",
        "dod clearance required",
        "active clearance required",
        "public trust clearance",
        "must obtain security clearance",
        "ability to obtain security clearance required",
        "clearance eligible",
    ]

    # Check if any keyword phrase appears (case-insensitive)
    for keyword in visa_blocker_keywords:
        if keyword in text:
            return True

    return False

def run_match_screener(description):
    """
    Returns the raw output string from the LLM, containing:
    Systems_Fit: ...
    Retrieval_Infra_Fit: ...
    Algorithmic_ML_Fit: ...
    Overall: ...
    Reason: ...
    """
    try:
        response = client.chat.completions.create(
            model=SCREENING_MODEL,
            messages=[
                {"role": "system", "content": MATCH_PROMPT},
                {"role": "user", "content": description[:MAX_DESC_LENGTH]}
            ],
            temperature=SCREENING_TEMP
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Match Screen Error: {e}")
        return "Overall: 0\nReason: Error during screening."

def run_combined_visa_senior_screener(description):
    """
    Combined screener for both Visa and Senior level checks.
    Returns (visa_status, visa_reason, senior_status, senior_reason)
    visa_status: "ACCEPT" or "REJECT"
    senior_status: "SENIOR" or "NOT_SENIOR"
    """
    try:
        response = client.chat.completions.create(
            model=SCREENING_MODEL,
            messages=[
                {"role": "system", "content": COMBINED_VISA_SENIOR_PROMPT},
                {"role": "user", "content": description[:MAX_DESC_LENGTH]}
            ],
            temperature=SCREENING_TEMP
        )
        content = response.choices[0].message.content.strip()
        lines = content.splitlines()
        
        # Default values (allow by default)
        visa_status = "ACCEPT"
        visa_reason = "Default allow"
        senior_status = "NOT_SENIOR"
        senior_reason = "Default allow"
        
        for line in lines:
            line = line.strip()
            if line.lower().startswith("visa_status:"):
                visa_status = line.split(":", 1)[1].strip().upper()
                if "REJECT" in visa_status:
                    visa_status = "REJECT"
                elif "ACCEPT" in visa_status:
                    visa_status = "ACCEPT"
            elif line.lower().startswith("visa_reason:"):
                visa_reason = line.split(":", 1)[1].strip()
            elif line.lower().startswith("senior_status:"):
                senior_status = line.split(":", 1)[1].strip().upper()
                if "NOT_SENIOR" in senior_status or "NOT SENIOR" in senior_status:
                    senior_status = "NOT_SENIOR"
                # If LLM explicitly says SENIOR, trust it, unless we want to override
                elif "SENIOR" in senior_status:
                    senior_status = "SENIOR"
                else:
                    senior_status = "NOT_SENIOR" # Default fallback
            elif line.lower().startswith("senior_reason:"):
                senior_reason = line.split(":", 1)[1].strip()
                
        return visa_status, visa_reason, senior_status, senior_reason
    except Exception as e:
        print(f"Combined Screen Error: {e}")
        return "ACCEPT", f"Error: {e}", "NOT_SENIOR", f"Error: {e}"

def extract_structured_jd_info(description):
    """
    Extract structured information from JD: tech stack, responsibilities, experience, metrics, salary.
    Returns a dictionary with parsed fields.
    """
    try:
        response = client.chat.completions.create(
            model=SCREENING_MODEL,
            messages=[
                {"role": "system", "content": STRUCTURED_EXTRACTION_PROMPT},
                {"role": "user", "content": description[:MAX_DESC_LENGTH]}
            ],
            temperature=0.1  # Low temperature for structured extraction
        )
        content = response.choices[0].message.content.strip()

        # Parse JSON response
        # Remove markdown code fences if present
        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()

        data = json.loads(content)

        # Convert lists to comma-separated strings for CSV storage
        result = {
            "technical_stack": ", ".join(data.get("technical_stack", [])) if isinstance(data.get("technical_stack"), list) else data.get("technical_stack", "N/A"),
            "key_responsibilities": " | ".join(data.get("key_responsibilities", [])) if isinstance(data.get("key_responsibilities"), list) else data.get("key_responsibilities", "N/A"),
            "required_experience": data.get("required_experience", "N/A"),
            "success_metrics": data.get("success_metrics", "N/A"),
            "salary_range": data.get("salary_range", "N/A"),
            "salary_is_estimated": data.get("salary_is_estimated", True)
        }

        return result
    except json.JSONDecodeError as e:
        print(f"Structured Extraction JSON Parse Error: {e}")
        return {
            "technical_stack": "N/A",
            "key_responsibilities": "N/A",
            "required_experience": "N/A",
            "success_metrics": "N/A",
            "salary_range": "N/A",
            "salary_is_estimated": True
        }
    except Exception as e:
        print(f"Structured Extraction Error: {e}")
        return {
            "technical_stack": "N/A",
            "key_responsibilities": "N/A",
            "required_experience": "N/A",
            "success_metrics": "N/A",
            "salary_range": "N/A",
            "salary_is_estimated": True
        }

def extract_jd_metadata(raw_jd_text):
    """
    Extract job metadata (title, company, location, etc.) from raw JD text.
    Returns a dictionary with: job_title, company, location, is_remote, job_url, description
    """
    try:
        response = client.chat.completions.create(
            model=SCREENING_MODEL,
            messages=[
                {"role": "system", "content": METADATA_EXTRACTION_PROMPT},
                {"role": "user", "content": raw_jd_text[:MAX_DESC_LENGTH]}
            ],
            temperature=0.1  # Low temperature for structured extraction
        )
        content = response.choices[0].message.content.strip()

        # Parse JSON response
        # Remove markdown code fences if present
        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()

        data = json.loads(content)

        # Ensure all required fields exist with defaults
        result = {
            "job_title": data.get("job_title", "Unknown Role"),
            "company": data.get("company", "Unknown Company"),
            "location": data.get("location", "Unknown"),
            "is_remote": data.get("is_remote", False),
            "job_url": data.get("job_url", ""),
            "description": data.get("description", raw_jd_text)
        }

        return result
    except json.JSONDecodeError as e:
        print(f"Metadata Extraction JSON Parse Error: {e}")
        # Fallback: return original text as description
        return {
            "job_title": "Unknown Role",
            "company": "Unknown Company",
            "location": "Unknown",
            "is_remote": False,
            "job_url": "",
            "description": raw_jd_text
        }
    except Exception as e:
        print(f"Metadata Extraction Error: {e}")
        return {
            "job_title": "Unknown Role",
            "company": "Unknown Company",
            "location": "Unknown",
            "is_remote": False,
            "job_url": "",
            "description": raw_jd_text
        }


def extract_manual_full_info(raw_jd_text):
    """
    Extract BOTH metadata AND structured details from raw JD in one go.
    Uses jd_extraction_manual.txt prompt.
    Returns a unified dictionary.
    """
    try:
        response = client.chat.completions.create(
            model=SCREENING_MODEL,
            messages=[
                {"role": "system", "content": MANUAL_FULL_EXTRACTION_PROMPT},
                {"role": "user", "content": raw_jd_text[:MAX_DESC_LENGTH]}
            ],
            temperature=0.1
        )
        content = response.choices[0].message.content.strip()

        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()

        data = json.loads(content)
        return data

    except Exception as e:
        print(f"Manual Full Extraction Error: {e}")
        # Return partial fallback
        return {
            "job_title": "Extraction Failed",
            "company": "Error",
            "location": "Unknown",
            "description": raw_jd_text,
            "technical_stack": "N/A",
            "key_responsibilities": "N/A"
        }
