"""Test configuration and fixtures."""

import os
import sys
from pathlib import Path

import pytest

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set test environment
os.environ["GOOGLE_API_KEY"] = "test_key"
os.environ["GEMINI_MODEL"] = "gemini-2.5-flash"  # Use valid Gemini 2.5 model
os.environ["CRON_MODE"] = "true"
os.environ["DEBUG"] = "true"


@pytest.fixture
def sample_job():
    """Sample job data for testing."""
    return {
        "id": "test-job-123",
        "company": "Test Corp",
        "role": "AI Engineer",
        "description": "Build AI systems using Python and LangChain",
        "job_url": "https://example.com/jobs/123",
        "company_website": "https://example.com",
        "location": "Remote",
        "source": "RemoteOK",
        "contact_email": "careers@example.com",
        "contact_type": "COMPANY",
        "email_source_url": "https://example.com/careers",
        "scraped_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_state(sample_job):
    """Sample job state for testing."""
    from app.state import create_initial_state

    return create_initial_state(sample_job["id"], sample_job)
