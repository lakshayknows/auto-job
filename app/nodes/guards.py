"""Guard nodes for legal, source, and send validation.

Implements safety checks as defined in:
- scraper.md (legal/source guards)
- send_guard.md (pre-send validation)
"""

import os
from pathlib import Path
from typing import Literal

from app.config import get_config, get_logger
from app.state import JobState

logger = get_logger("guards")

# Blocked domains for legal compliance
BLOCKED_DOMAINS = [
    "linkedin.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
]

# Allowed email prefixes
ALLOWED_EMAIL_PREFIXES = ["careers", "jobs", "hiring", "hr", "talent", "recruiting"]


def legal_guard(state: JobState) -> JobState:
    """LangGraph node: Validate job source is legal.

    Checks:
    - Source is not from blocked domains (LinkedIn, etc.)
    - Job URL is accessible
    - No personal profile data

    Args:
        state: Current job state

    Returns:
        Updated state with legal_check_passed flag
    """
    errors = state.get("errors", [])
    job_data = state.get("job_data", {})

    # Check for blocked sources
    job_url = job_data.get("job_url", "")
    company_url = job_data.get("company_website", "")
    email_source = state.get("email_source_url", "")

    for url in [job_url, company_url, email_source]:
        if url:
            url_lower = url.lower()
            for blocked in BLOCKED_DOMAINS:
                if blocked in url_lower:
                    logger.warning(f"Blocked domain detected: {blocked} in {url}")
                    return {
                        **state,
                        "legal_check_passed": False,
                        "errors": errors + [f"Blocked domain: {blocked}"],
                        "should_skip": True,
                        "skip_reason": f"Legal guard failed: blocked domain {blocked}",
                    }

    # Check source is recognized
    source = job_data.get("source", "")
    allowed_sources = ["RemoteOK", "HackerNews", "GoogleJobs", "Indeed", "AngelList"]

    if source and source not in allowed_sources:
        logger.warning(f"Unrecognized source: {source}")
        return {
            **state,
            "legal_check_passed": False,
            "errors": errors + [f"Unrecognized source: {source}"],
            "should_skip": True,
            "skip_reason": f"Legal guard failed: unrecognized source {source}",
        }

    logger.info(f"Legal check passed for job {state.get('job_id')}")
    return {
        **state,
        "legal_check_passed": True,
    }


def route_after_legal_guard(state: JobState) -> Literal["pass", "fail"]:
    """Route based on legal guard result.

    Args:
        state: Current job state

    Returns:
        'pass' if legal check passed, 'fail' otherwise
    """
    if state.get("legal_check_passed", False):
        return "pass"
    return "fail"


def source_guard(state: JobState) -> JobState:
    """Validate email source is appropriate.

    Checks email prefix is from allowed types:
    - careers@, jobs@, hiring@, hr@, talent@

    Args:
        state: Current job state

    Returns:
        Updated state with validation result
    """
    errors = state.get("errors", [])
    contact_email = state.get("contact_email")

    if not contact_email:
        logger.info("No contact email to validate")
        return state

    # Check email prefix
    local_part = contact_email.split("@")[0].lower()
    is_valid = any(prefix in local_part for prefix in ALLOWED_EMAIL_PREFIXES)

    # Personal emails only allowed if contact_type is HR
    if not is_valid:
        contact_type = state.get("contact_type", "UNKNOWN")
        if contact_type == "HR":
            logger.info(f"Personal email allowed for HR contact: {contact_email}")
            is_valid = True

    if not is_valid:
        logger.warning(f"Invalid email prefix: {contact_email}")
        return {
            **state,
            "errors": errors + [f"Email prefix not allowed: {contact_email}"],
            "contact_email": None,  # Clear invalid email
        }

    logger.info(f"Email source validated: {contact_email}")
    return state


def send_guard(state: JobState) -> JobState:
    """LangGraph node: Final safety check before email dispatch.

    Checks per send_guard.md:
    - approval_status == APPROVED
    - contact_email is not null
    - resume PDF exists
    - email not already sent
    - CRON_MODE == false

    Args:
        state: Current job state

    Returns:
        Updated state with send_guard_passed flag
    """
    config = get_config()
    errors = state.get("errors", [])
    checks_failed = []

    # Check 1: Approval status
    if state.get("approval_status") != "APPROVED":
        checks_failed.append(f"Not approved: status={state.get('approval_status')}")

    # Check 2: Contact email exists
    if not state.get("contact_email"):
        checks_failed.append("No contact email")

    # Check 3: Resume PDF exists
    resume_pdf = state.get("resume_pdf_path")
    if not resume_pdf or not Path(resume_pdf).exists():
        checks_failed.append(f"Resume PDF missing: {resume_pdf}")

    # Check 4: Not already sent
    if state.get("sent", False):
        checks_failed.append("Email already sent")

    # Check 5: CRON_MODE is false
    if config.cron_mode:
        checks_failed.append("CRON_MODE is active - sending blocked")

    if checks_failed:
        logger.warning(f"Send guard failed: {checks_failed}")
        return {
            **state,
            "send_guard_passed": False,
            "errors": errors + checks_failed,
        }

    logger.info(f"Send guard passed for job {state.get('job_id')}")
    return {
        **state,
        "send_guard_passed": True,
    }


def route_after_send_guard(state: JobState) -> Literal["pass", "fail"]:
    """Route based on send guard result.

    Args:
        state: Current job state

    Returns:
        'pass' if send guard passed, 'fail' otherwise
    """
    if state.get("send_guard_passed", False):
        return "pass"
    return "fail"


def cost_guard(state: JobState) -> JobState:
    """Check if cost limits have been exceeded.

    Args:
        state: Current job state

    Returns:
        Updated state with should_skip if limits exceeded
    """
    config = get_config()
    llm_calls = state.get("llm_calls", 0)
    total_tokens = state.get("total_tokens", 0)

    if llm_calls >= config.cost.max_llm_calls_per_run:
        logger.warning(f"LLM call limit reached: {llm_calls}")
        return {
            **state,
            "should_skip": True,
            "skip_reason": f"LLM call limit exceeded: {llm_calls}",
            "errors": state.get("errors", []) + [f"Cost limit: {llm_calls} LLM calls"],
        }

    if total_tokens >= config.cost.max_tokens_per_run:
        logger.warning(f"Token limit reached: {total_tokens}")
        return {
            **state,
            "should_skip": True,
            "skip_reason": f"Token limit exceeded: {total_tokens}",
            "errors": state.get("errors", []) + [f"Cost limit: {total_tokens} tokens"],
        }

    return state


def cron_mode_guard(state: JobState) -> JobState:
    """Block LLM calls and sending in CRON_MODE.

    Args:
        state: Current job state

    Returns:
        Updated state with should_skip if CRON_MODE active
    """
    config = get_config()

    if config.cron_mode:
        logger.info("CRON_MODE active - blocking LLM calls and sending")
        return {
            **state,
            "should_skip": True,
            "skip_reason": "CRON_MODE active",
        }

    return state
