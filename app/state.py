"""Central state model for job application pipeline."""

from typing import Literal, Optional, TypedDict


class JobData(TypedDict, total=False):
    """Job listing data structure."""

    company: str
    role: str
    description: str
    job_url: str
    company_website: str
    location: str
    source: str
    scraped_at: str


class RAGContext(TypedDict, total=False):
    """RAG retrieval context structure."""

    job_skills: list[str]
    job_responsibilities: list[str]
    job_tech_stack: list[str]
    resume_experience: list[str]
    resume_projects: list[str]
    resume_skills: list[str]


class JobState(TypedDict, total=False):
    """Central state for job application pipeline.

    All fields are optional to allow incremental state building.
    State must be serializable for checkpointing.
    """

    # Job identification
    job_id: str
    job_data: JobData

    # Contact information
    contact_email: Optional[str]
    contact_type: Literal["COMPANY", "HR", "UNKNOWN"]
    email_source_url: Optional[str]

    # Resume artifacts
    resume_tex_path: Optional[str]
    resume_pdf_path: Optional[str]

    # Email artifacts
    email_draft: Optional[str]
    email_subject: Optional[str]

    # RAG context
    rag_context: Optional[RAGContext]

    # Approval workflow
    approval_status: Literal["PENDING", "APPROVED", "REJECTED"]
    sent: bool

    # Error tracking
    errors: list[str]

    # Cost tracking
    llm_calls: int
    total_tokens: int

    # Guard flags
    legal_check_passed: bool
    send_guard_passed: bool

    # Flow control
    should_skip: bool
    skip_reason: Optional[str]


def create_initial_state(job_id: str, job_data: dict) -> JobState:
    """Create initial state for a job application.

    Args:
        job_id: Unique identifier for the job
        job_data: Job listing data

    Returns:
        Initialized JobState with defaults
    """
    return JobState(
        job_id=job_id,
        job_data=job_data,
        contact_email=job_data.get("contact_email"),
        contact_type=job_data.get("contact_type", "UNKNOWN"),
        email_source_url=job_data.get("email_source_url"),
        resume_tex_path=None,
        resume_pdf_path=None,
        email_draft=None,
        email_subject=None,
        rag_context=None,
        approval_status="PENDING",
        sent=False,
        errors=[],
        llm_calls=0,
        total_tokens=0,
        legal_check_passed=False,
        send_guard_passed=False,
        should_skip=False,
        skip_reason=None,
    )
