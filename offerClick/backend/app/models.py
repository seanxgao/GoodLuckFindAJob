from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel


class JobStatus(str, Enum):
    NOT_APPLIED = "not_applied"
    APPLIED = "applied"
    SKIPPED = "skipped"
    STARRED = "starred"


class JDStructured(BaseModel):
    technical_stack: str  # Comma-separated tech stack
    key_responsibilities: str  # Pipe-separated responsibilities
    required_experience: str
    success_metrics: str
    salary_range: str
    salary_is_estimated: bool


class MatchExplanation(BaseModel):
    strong_fit: List[str]
    gaps: List[str]


class RecommendedProjects(BaseModel):
    scope: List[str]
    edge: List[str]
    whisper: List[str]
    alibaba: Optional[List[str]] = []
    craes: Optional[List[str]] = []


class ResumeVersion(BaseModel):
    pdf_path: str
    text_path: str
    version_id: str
    created_at: str
    bullets: Optional[Dict[str, List[str]]] = {}


class Job(BaseModel):
    id: str
    company: str
    role: str
    location: str
    url: Optional[str] = ""
    remote: bool
    match_score: int
    tags: List[str]
    status: JobStatus
    source: Optional[str] = "Unknown"  # Added source field
    jd_raw: str
    visa_analysis: Optional[str] = ""
    jd_structured: JDStructured
    match_explanation: MatchExplanation
    recommended_projects: RecommendedProjects
    resume_versions: Optional[List[ResumeVersion]] = []


class JobUpdate(BaseModel):
    status: Optional[JobStatus] = None


class ResumeGenerationResult(BaseModel):
    pdf_path: str
    text_path: str
    version_id: str
    created_at: str
    bullets: Optional[Dict[str, List[str]]] = {}

