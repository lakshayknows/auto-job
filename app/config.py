"""
Configuration module for job automation system.
Loads environment variables and provides centralized configuration.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Centralized configuration for the job automation system."""

    # API Keys (using Google Gemini as primary LLM)
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    )

    # SMTP Configuration
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.office365.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_EMAIL: str = os.getenv("SMTP_EMAIL", "connect.lakshay@outlook.com")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    # Cost Control
    MAX_LLM_CALLS_PER_RUN: int = int(os.getenv("MAX_LLM_CALLS_PER_RUN", "25"))
    CRON_MODE: bool = os.getenv("CRON_MODE", "false").lower() == "true"

    # Paths
    DATA_DIR: Path = BASE_DIR / "data"
    CACHE_DIR: Path = BASE_DIR / "cache"
    RESUME_DIR: Path = BASE_DIR / "resume"
    PROMPTS_DIR: Path = BASE_DIR / "prompts"
    RAG_INDEX_DIR: Path = BASE_DIR / "rag_index"

    # Data files
    JOBS_JSON: Path = DATA_DIR / "jobs.json"
    JOBS_CSV: Path = DATA_DIR / "jobs.csv"
    CONTACTS_JSON: Path = DATA_DIR / "contacts.json"
    CONTACTS_CSV: Path = DATA_DIR / "contacts.csv"
    APPROVALS_JSON: Path = DATA_DIR / "approvals.json"
    APPROVALS_CSV: Path = DATA_DIR / "approvals.csv"

    # Resume paths
    BASE_RESUME_TEX: Path = RESUME_DIR / "base_resume.tex"
    COMPILED_RESUME_DIR: Path = RESUME_DIR / "compiled"

    # Cache paths
    EMBEDDINGS_CACHE: Path = CACHE_DIR / "embeddings"
    RESUMES_CACHE: Path = CACHE_DIR / "resumes"
    EMAILS_CACHE: Path = CACHE_DIR / "emails"

    # RAG index paths
    JOB_INDEX_DIR: Path = RAG_INDEX_DIR / "job_index"
    RESUME_INDEX_DIR: Path = RAG_INDEX_DIR / "resume_index"

    # Scraping limits
    MAX_JOBS_PER_RUN: int = 100
    CRAWL_DEPTH: int = 1
    ALLOWED_PATHS: list = ["/careers", "/jobs", "/contact", "/about", "/hiring"]

    # LLM Model Configuration (Google Gemini)
    LLM_MODEL: str = "gemini-1.5-flash"
    EMBEDDING_MODEL: str = "models/embedding-001"

    @classmethod
    def ensure_directories(cls) -> None:
        """Create all required directories if they don't exist."""
        directories = [
            cls.DATA_DIR,
            cls.CACHE_DIR,
            cls.EMBEDDINGS_CACHE,
            cls.RESUMES_CACHE,
            cls.EMAILS_CACHE,
            cls.COMPILED_RESUME_DIR,
            cls.JOB_INDEX_DIR,
            cls.RESUME_INDEX_DIR,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls) -> bool:
        """Validate that required configuration is present."""
        if not cls.GOOGLE_API_KEY:
            print("WARNING: GOOGLE_API_KEY not set")
            return False
        return True


# LLM call counter for cost control
class LLMCallCounter:
    """Track LLM API calls to enforce cost limits."""

    def __init__(self):
        self.count = 0
        self.max_calls = Config.MAX_LLM_CALLS_PER_RUN

    def increment(self) -> bool:
        """Increment counter. Returns False if limit exceeded."""
        self.count += 1
        if self.count > self.max_calls:
            print(f"WARNING: LLM call limit exceeded ({self.max_calls})")
            return False
        return True

    def can_call(self) -> bool:
        """Check if we can make another LLM call."""
        return self.count < self.max_calls

    def reset(self) -> None:
        """Reset the counter."""
        self.count = 0


# Global counter instance
llm_counter = LLMCallCounter()
