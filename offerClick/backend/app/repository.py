import json
import csv
import hashlib
import time
from pathlib import Path
from typing import List, Optional
from app.models import Job, JobStatus, JDStructured, MatchExplanation, RecommendedProjects


class JobRepository:
    def __init__(self, data_file: str = None):
        if data_file is None:
            # Default to the daily good_jobs.csv file
            project_root = Path(__file__).parent.parent.parent.parent
            data_file = project_root / "data" / "daily" / "good_jobs.csv"
            
            print(f"[DEBUG] Configured to use data file: {data_file}")
            
            if not data_file.exists():
                print(f"[WARNING] Data file does not exist at {data_file}")
                # Fallback logic could go here if needed, but for now we stick to the requirement
        
        self.data_file = Path(data_file)
        self._is_json = self.data_file.suffix.lower() == '.json'
        
        # Status file location: always next to the data file or in the same directory
        self._status_file = self.data_file.parent / "job_statuses.json"

        print(f"[DEBUG] Status file: {self._status_file}")
        self._ensure_status_file_exists()

        # Simple in-memory cache for faster reads
        self._cache = None
        self._cache_timestamp = 0
        self._cache_ttl = 3  # Cache for 3 seconds (good for UI without staleness)

    def _ensure_status_file_exists(self):
        """Create empty status file if it doesn't exist"""
        if not self._status_file.exists():
            self._status_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._status_file, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _invalidate_cache(self):
        """Invalidate the cache"""
        self._cache = None
        self._cache_timestamp = 0

    def _load_statuses(self) -> dict:
        """Load job statuses from JSON file"""
        try:
            with open(self._status_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_statuses(self, statuses: dict):
        """Save job statuses to JSON file"""
        self._status_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._status_file, "w", encoding="utf-8") as f:
            json.dump(statuses, f, indent=2, ensure_ascii=False)

    def _generate_job_id(self, company: str, title: str, url: str) -> str:
        """Generate a unique job ID from company, title, and URL"""
        combined = f"{company}|{title}|{url}"
        return hashlib.md5(combined.encode()).hexdigest()[:12]

    def _parse_match_analysis(self, overall_match: str, match_reason: str, 
                             systems_fit: str = "", retrieval_fit: str = "", 
                             algorithmic_fit: str = "") -> tuple:
        """Parse match analysis fields to extract match score and explanation"""
        # Convert overall rating to match score
        match_score = 50
        try:
            match_score = int(float(overall_match))
        except (ValueError, TypeError):
            overall_upper = (overall_match or "").upper()
            if "STRONG MATCH" in overall_upper:
                match_score = 85
            elif "MEDIUM MATCH" in overall_upper:
                match_score = 70
        
        # Parse match reason into bullets
        strong_fit = []
        gaps = []
        
        if match_reason:
            # Split by | or newline, then extract bullet points
            reasons = match_reason.replace("|", "\n").split("\n")
            for reason in reasons:
                reason = reason.strip()
                if not reason:
                    continue
                # Remove leading "- " or "| " if present
                reason = reason.lstrip("- |").strip()
                if reason:
                    # Check if it's a gap (contains words like "less", "weak", "not", "lack")
                    is_gap = any(word in reason.lower() for word in ["less", "weak", "not primary", "lack", "limited", "no direct"])
                    if is_gap:
                        gaps.append(reason)
                    else:
                        strong_fit.append(reason)
        
        # Helper to check fit
        def is_good_fit(val):
            try:
                return float(val) >= 60
            except (ValueError, TypeError):
                return str(val).upper() in ["HIGH", "MEDIUM"]

        # If we have fit ratings, add them to strong_fit
        if is_good_fit(systems_fit):
            strong_fit.append(f"Systems fit: {systems_fit}")
        if is_good_fit(retrieval_fit):
            strong_fit.append(f"Retrieval/Infra fit: {retrieval_fit}")
        if is_good_fit(algorithmic_fit):
            strong_fit.append(f"Algorithmic/ML fit: {algorithmic_fit}")
        
        # Limit to 3 items each
        strong_fit = strong_fit[:3] if strong_fit else ["Strong match based on screening analysis"]
        gaps = gaps[:3] if gaps else []
        
        return match_score, MatchExplanation(
            strong_fit=strong_fit,
            gaps=gaps
        )

    def _csv_row_to_job(self, row: dict, statuses: dict) -> Job:
        """Convert a CSV row to a Job model"""
        company = row.get("COMPANY", "Unknown Company")
        title = row.get("TITLE", "Unknown Title")
        url = row.get("JOB_URL", "")
        job_id = self._generate_job_id(company, title, url)
        
        # Get status from statuses dict, default to not_applied
        status = JobStatus(statuses.get(job_id, "not_applied"))
        
        # Parse location and remote
        location = row.get("LOCATION", "Unknown")
        is_remote = row.get("IS_REMOTE", False)
        if isinstance(is_remote, str):
            is_remote = is_remote.lower() in ("true", "1", "yes")
        elif isinstance(is_remote, bool):
            is_remote = is_remote
        
        # Parse match analysis from CSV columns
        overall_match = row.get("OVERALL_MATCH", "")
        match_reason = row.get("MATCH_REASON", "")
        systems_fit = row.get("SYSTEMS_FIT", "")
        retrieval_fit = row.get("RETRIEVAL_INFRA_FIT", "")
        algorithmic_fit = row.get("ALGORITHMIC_ML_FIT", "")
        visa_analysis = row.get("VISA_ANALYSIS", "") # Extract Visa Analysis
        source = row.get("SOURCE", "Unknown") # Extract Source
        description = "" # DESCRIPTION column removed from CSV, use empty string
        
        match_score, match_explanation = self._parse_match_analysis(
            overall_match, match_reason, systems_fit, retrieval_fit, algorithmic_fit
        )
        
        # Extract tags from fit ratings and structured fields
        tags = []

        # Use fit ratings to determine tags
        def is_good_fit(val):
            try:
                return float(val) >= 60
            except (ValueError, TypeError):
                return str(val).upper() in ["HIGH", "MEDIUM"]

        if is_good_fit(systems_fit):
            tags.append("backend")
        if is_good_fit(retrieval_fit):
            tags.append("retrieval")
            tags.append("infra")
        if is_good_fit(algorithmic_fit):
            tags.append("ML")

        # Fallback: extract from structured fields if no fit ratings
        if not tags:
            # Combine technical stack and responsibilities for keyword search
            tech_stack = row.get("TECHNICAL_STACK", "").lower()
            responsibilities = row.get("KEY_RESPONSIBILITIES", "").lower()
            combined_text = f"{tech_stack} {responsibilities}"

            if "backend" in combined_text or "distributed systems" in combined_text or "microservices" in combined_text:
                tags.append("backend")
            if "ml" in combined_text or "machine learning" in combined_text or "ai" in combined_text or "deep learning" in combined_text:
                tags.append("ML")
            if "infra" in combined_text or "infrastructure" in combined_text or "devops" in combined_text or "kubernetes" in combined_text:
                tags.append("infra")
            if "retrieval" in combined_text or "search" in combined_text or "ranking" in combined_text or "recommendation" in combined_text:
                tags.append("retrieval")

        # Default tag if none found
        if not tags:
            tags = ["SWE-generalist"]
        
        # Remove duplicates while preserving order
        seen = set()
        tags = [t for t in tags if not (t in seen or seen.add(t))]
        
        # Read structured JD information from CSV columns (generated by screener)
        technical_stack = row.get("TECHNICAL_STACK", "N/A")
        key_responsibilities = row.get("KEY_RESPONSIBILITIES", "N/A")
        required_experience = row.get("REQUIRED_EXPERIENCE", "N/A")
        success_metrics = row.get("SUCCESS_METRICS", "N/A")
        salary_range = row.get("SALARY_RANGE", "N/A")
        salary_is_estimated = row.get("SALARY_IS_ESTIMATED", "true")

        # Convert salary_is_estimated to boolean
        if isinstance(salary_is_estimated, str):
            salary_is_estimated = salary_is_estimated.lower() in ("true", "1", "yes")
        elif not isinstance(salary_is_estimated, bool):
            salary_is_estimated = True  # Default to true if unclear

        jd_structured = JDStructured(
            technical_stack=technical_stack,
            key_responsibilities=key_responsibilities,
            required_experience=required_experience,
            success_metrics=success_metrics,
            salary_range=salary_range,
            salary_is_estimated=salary_is_estimated
        )
        
        # Default recommended projects (empty for now - would be generated by converter)
        recommended_projects = RecommendedProjects(
            scope=[],
            edge=[],
            whisper=[]
        )
        
        return Job(
            id=job_id,
            company=company,
            role=title,
            location=location,
            url=url,
            remote=is_remote,
            match_score=match_score,
            tags=tags,
            status=status,
            source=source,
            jd_raw=description,
            visa_analysis=visa_analysis,
            jd_structured=jd_structured,
            match_explanation=match_explanation,
            recommended_projects=recommended_projects,
            resume_versions=[]
        )

    def _json_to_job(self, job_data: dict, statuses: dict) -> Job:
        """Convert a JSON job object to a Job model"""
        job_id = job_data.get("id", "")
        status = JobStatus(statuses.get(job_id, job_data.get("status", "not_applied")))
        
        # Parse match_explanation
        match_expl = job_data.get("match_explanation", {})
        match_explanation = MatchExplanation(
            strong_fit=match_expl.get("strong_fit", []),
            gaps=match_expl.get("gaps", [])
        )
        
        # Parse jd_structured
        jd_struct = job_data.get("jd_structured", {})
        jd_structured = JDStructured(
            technical_stack=jd_struct.get("technical_stack", "N/A"),
            key_responsibilities=jd_struct.get("key_responsibilities", "N/A"),
            required_experience=jd_struct.get("required_experience", "N/A"),
            success_metrics=jd_struct.get("success_metrics", "N/A"),
            salary_range=jd_struct.get("salary_range", "N/A"),
            salary_is_estimated=jd_struct.get("salary_is_estimated", True)
        )
        
        # Parse recommended_projects
        rec_proj = job_data.get("recommended_projects", {})
        recommended_projects = RecommendedProjects(
            scope=rec_proj.get("scope", []),
            edge=rec_proj.get("edge", []),
            whisper=rec_proj.get("whisper", [])
        )
        
        # Parse resume_versions
        resume_versions = []
        if "resume_versions" in job_data:
            from app.models import ResumeVersion
            resume_versions = [ResumeVersion(**v) for v in job_data["resume_versions"]]
        
        return Job(
            id=job_id,
            company=job_data.get("company", "Unknown Company"),
            role=job_data.get("role", "Unknown Title"),
            location=job_data.get("location", "Unknown"),
            remote=job_data.get("remote", False),
            match_score=job_data.get("match_score", 50),
            tags=job_data.get("tags", []),
            status=status,
            source=job_data.get("source", "Unknown"),
            jd_raw=job_data.get("jd_raw", ""),
            jd_structured=jd_structured,
            match_explanation=match_explanation,
            recommended_projects=recommended_projects,
            resume_versions=resume_versions
        )

    def get_all(self) -> List[Job]:
        """Read all jobs from CSV or JSON file (with simple caching)"""
        # Check cache first
        current_time = time.time()
        if self._cache is not None and (current_time - self._cache_timestamp) < self._cache_ttl:
            print(f"[DEBUG] Returning cached jobs ({len(self._cache)} jobs)")
            return self._cache

        print(f"[DEBUG] get_all() called, data_file: {self.data_file}, exists: {self.data_file.exists()}")

        if not self.data_file.exists():
            error_msg = f"Data file not found: {self.data_file}. Please ensure the file exists."
            print(f"ERROR: {error_msg}")
            raise FileNotFoundError(error_msg)
        
        try:
            statuses = self._load_statuses()
            print(f"[DEBUG] Loaded {len(statuses)} job statuses")
            jobs = []
            
            if self._is_json:
                # Read from JSON file
                print(f"[DEBUG] Reading from JSON file...")
                with open(self.data_file, "r", encoding="utf-8") as f:
                    job_list = json.load(f)
                    print(f"[DEBUG] Found {len(job_list)} jobs in JSON file")
                    for idx, job_data in enumerate(job_list):
                        try:
                            job = self._json_to_job(job_data, statuses)
                            jobs.append(job)
                        except Exception as e:
                            print(f"Error parsing job {idx} from JSON: {e}")
                            import traceback
                            traceback.print_exc()
                            continue
            else:
                # Read from CSV file
                print(f"[DEBUG] Reading from CSV file...")
                with open(self.data_file, "r", encoding="utf-8", errors="ignore") as f:
                    reader = csv.DictReader(f)
                    row_count = 0
                    for row in reader:
                        row_count += 1
                        try:
                            job = self._csv_row_to_job(row, statuses)
                            jobs.append(job)
                        except Exception as e:
                            print(f"Error parsing job row {row_count}: {e}")
                            import traceback
                            traceback.print_exc()
                            continue
                    print(f"[DEBUG] Processed {row_count} CSV rows, created {len(jobs)} jobs")

            # Cache the results
            self._cache = jobs
            self._cache_timestamp = time.time()
            print(f"[DEBUG] Cached {len(jobs)} jobs")

            print(f"[DEBUG] Returning {len(jobs)} jobs")
            return jobs
        except FileNotFoundError:
            raise
        except Exception as e:
            error_msg = f"Error reading data file {self.data_file}: {str(e)}"
            print(f"ERROR: {error_msg}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(error_msg) from e

    def get_by_id(self, job_id: str) -> Optional[Job]:
        """Get a single job by ID"""
        jobs = self.get_all()
        for job in jobs:
            if job.id == job_id:
                # Load resume versions if they exist
                resume_file = self.data_file.parent / "resume_versions.json"
                try:
                    with open(resume_file, "r", encoding="utf-8") as f:
                        versions = json.load(f)
                        if job_id in versions:
                            from app.models import ResumeVersion
                            job.resume_versions = [ResumeVersion(**v) for v in versions[job_id]]
                            
                            # Hydrate recommended_projects from the latest version's bullets
                            if job.resume_versions:
                                latest_version = job.resume_versions[-1]
                                
                                # If bullets are empty in memory, try to load from disk
                                if not latest_version.bullets:
                                    try:
                                        pdf_path = Path(latest_version.pdf_path)
                                        bullets_path = pdf_path.with_name(f"{latest_version.version_id}_bullets.json")
                                        if bullets_path.exists():
                                            with open(bullets_path, "r", encoding="utf-8") as f:
                                                latest_version.bullets = json.load(f)
                                                print(f"[DEBUG] Lazy loaded bullets for {job_id} from {bullets_path}")
                                    except Exception as e:
                                        print(f"[WARN] Failed to lazy load bullets for {job_id}: {e}")
                                
                                if latest_version.bullets:
                                    # Map the keys from bullets.json to the RecommendedProjects model
                                    mapping = {
                                        "%%SPECTRAL_BULLETS_BLOCK%%": "scope",
                                        "%%EDGE_BULLETS_BLOCK%%": "edge",
                                        "%%WHISPER_BULLETS_BLOCK%%": "whisper",
                                        "%%ALIBABA_BULLETS_BLOCK%%": "alibaba",
                                        "%%CRAES_BULLETS_BLOCK%%": "craes"
                                    }
                                    
                                    normalized_bullets = {}
                                    for marker, bullets in latest_version.bullets.items():
                                        # Handle both mapped keys and direct keys (future proofing)
                                        field_name = mapping.get(marker, marker)
                                        normalized_bullets[field_name] = bullets
                                        
                                        if hasattr(job.recommended_projects, field_name):
                                            setattr(job.recommended_projects, field_name, bullets)
                                    
                                    # Update bullets to use normalized keys
                                    latest_version.bullets = normalized_bullets


                except (FileNotFoundError, json.JSONDecodeError):
                    pass
                return job
        return None

    def update_status(self, job_id: str, status: JobStatus) -> Optional[Job]:
        """Update job status and persist to status file"""
        statuses = self._load_statuses()
        statuses[job_id] = status.value
        self._save_statuses(statuses)
        self._invalidate_cache()  # Invalidate cache on update
        
        # Return updated job
        jobs = self.get_all()
        for job in jobs:
            if job.id == job_id:
                return job
        return None

    def add_resume_version(self, job_id: str, resume_version: dict) -> Optional[Job]:
        """Add a resume version to a job (stored separately)"""
        # Store resume versions in a separate file
        resume_file = self.data_file.parent / "resume_versions.json"
        try:
            with open(resume_file, "r", encoding="utf-8") as f:
                versions = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            versions = {}

        if job_id not in versions:
            versions[job_id] = []

        from app.models import ResumeVersion
        versions[job_id].append(ResumeVersion(**resume_version).model_dump())

        with open(resume_file, "w", encoding="utf-8") as f:
            json.dump(versions, f, indent=2, ensure_ascii=False)

        self._invalidate_cache()  # Invalidate cache on update

        # Return updated job
        jobs = self.get_all()
        for job in jobs:
            if job.id == job_id:
                # Load resume versions for this job
                if job_id in versions:
                    job.resume_versions = [ResumeVersion(**v) for v in versions[job_id]]

                    # Hydrate recommended_projects from the latest version's bullets
                    if job.resume_versions:
                        latest_version = job.resume_versions[-1]

                        # If bullets are empty in memory, try to load from disk
                        if not latest_version.bullets:
                            try:
                                pdf_path = Path(latest_version.pdf_path)
                                bullets_path = pdf_path.with_name(f"{latest_version.version_id}_bullets.json")
                                if bullets_path.exists():
                                    with open(bullets_path, "r", encoding="utf-8") as f:
                                        latest_version.bullets = json.load(f)
                            except Exception as e:
                                print(f"[WARN] Failed to lazy load bullets for {job_id}: {e}")

                        if latest_version.bullets:
                            mapping = {
                                "%%SPECTRAL_BULLETS_BLOCK%%": "scope",
                                "%%EDGE_BULLETS_BLOCK%%": "edge",
                                "%%WHISPER_BULLETS_BLOCK%%": "whisper",
                                "%%ALIBABA_BULLETS_BLOCK%%": "alibaba",
                                "%%CRAES_BULLETS_BLOCK%%": "craes"
                            }

                            normalized_bullets = {}
                            for marker, bullets in latest_version.bullets.items():
                                # Handle both mapped keys and direct keys (future proofing)
                                field_name = mapping.get(marker, marker)
                                normalized_bullets[field_name] = bullets

                                if hasattr(job.recommended_projects, field_name):
                                    setattr(job.recommended_projects, field_name, bullets)

                            # Update bullets to use normalized keys
                            latest_version.bullets = normalized_bullets

                return job
        return None

    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job from good_jobs.csv and clean up associated files.
        Returns True if successful, False if job not found.
        """
        # First, get the job to ensure it exists
        job = self.get_by_id(job_id)
        if not job:
            return False

        # For CSV files, we need to read all rows and write back excluding the deleted job
        if not self._is_json:
            # Read all rows from CSV
            rows = []
            with open(self.data_file, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for row in reader:
                    # Generate job_id for this row to check if it matches
                    row_job_id = self._generate_job_id(
                        row.get("COMPANY", ""),
                        row.get("TITLE", ""),
                        row.get("JOB_URL", "")
                    )
                    if row_job_id != job_id:
                        rows.append(row)

            # Write back to CSV (excluding the deleted job)
            with open(self.data_file, "w", encoding="utf-8", newline="") as f:
                if fieldnames and rows:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                elif fieldnames and not rows:
                    # If we deleted the last row, still write the header
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()

        else:
            # For JSON files
            with open(self.data_file, "r", encoding="utf-8") as f:
                jobs = json.load(f)

            # Filter out the job with matching ID
            jobs = [j for j in jobs if j.get("id") != job_id]

            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(jobs, f, indent=2, ensure_ascii=False)

        # Remove from status file
        statuses = self._load_statuses()
        if job_id in statuses:
            del statuses[job_id]
            self._save_statuses(statuses)

        # Remove from resume versions
        resume_file = self.data_file.parent / "resume_versions.json"
        if resume_file.exists():
            try:
                with open(resume_file, "r", encoding="utf-8") as f:
                    versions = json.load(f)
                if job_id in versions:
                    del versions[job_id]
                    with open(resume_file, "w", encoding="utf-8") as f:
                        json.dump(versions, f, indent=2, ensure_ascii=False)
            except (FileNotFoundError, json.JSONDecodeError):
                pass

        self._invalidate_cache()  # Invalidate cache on deletion
        print(f"[INFO] Deleted job {job_id} from data files")
        return True

