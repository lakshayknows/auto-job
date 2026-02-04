"""Approval node with LangGraph interrupt.

Implements human-in-the-loop approval as defined in approval_guard.md.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.config import DATA_DIR, get_logger, log_activity
from app.state import JobState

logger = get_logger("approval")

# Approvals file path
APPROVALS_FILE = DATA_DIR / "approvals.json"


def load_approvals() -> dict:
    """Load approvals from file.

    Returns:
        Dict of job_id -> approval record
    """
    if APPROVALS_FILE.exists():
        with open(APPROVALS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_approval(job_id: str, status: str, metadata: dict = None):
    """Save approval decision to file.

    Args:
        job_id: Job identifier
        status: Approval status
        metadata: Additional metadata
    """
    approvals = load_approvals()

    approvals[job_id] = {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata or {},
    }

    APPROVALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(APPROVALS_FILE, "w") as f:
        json.dump(approvals, f, indent=2)

    logger.info(f"Saved approval: {job_id} -> {status}")


def get_approval_status(job_id: str) -> str:
    """Get approval status for a job.

    Args:
        job_id: Job identifier

    Returns:
        Approval status (PENDING, APPROVED, REJECTED)
    """
    approvals = load_approvals()
    record = approvals.get(job_id, {})
    return record.get("status", "PENDING")


def request_approval(state: JobState) -> JobState:
    """LangGraph node: Request human approval.

    This node is configured as an interrupt point in the graph.
    When reached, execution pauses until approval is provided.

    Args:
        state: Current job state

    Returns:
        Updated state (unchanged for interrupt)
    """
    job_id = state.get("job_id", "unknown")

    # Check if already approved/rejected
    existing_status = get_approval_status(job_id)
    if existing_status in ["APPROVED", "REJECTED"]:
        logger.info(f"Using existing approval: {job_id} -> {existing_status}")
        return {
            **state,
            "approval_status": existing_status,
        }

    # Log approval request
    job_data = state.get("job_data", {})
    email_draft = state.get("email_draft", "")
    contact_email = state.get("contact_email", "")

    logger.info(f"""
========================================
APPROVAL REQUIRED
========================================
Job ID: {job_id}
Company: {job_data.get('company', 'Unknown')}
Role: {job_data.get('role', 'Unknown')}
Contact: {contact_email}

Email Draft:
{email_draft}
========================================
""")

    # State remains PENDING - graph will interrupt here
    return {
        **state,
        "approval_status": "PENDING",
    }


def approve_job(job_id: str, notes: str = "") -> bool:
    """Approve a job application.

    Args:
        job_id: Job identifier
        notes: Optional approval notes

    Returns:
        True if approval saved
    """
    save_approval(job_id, "APPROVED", {"notes": notes})
    log_activity("APPROVED", job_id, "Unknown", f"Notes: {notes}")
    return True


def reject_job(job_id: str, reason: str = "") -> bool:
    """Reject a job application.

    Args:
        job_id: Job identifier
        reason: Rejection reason

    Returns:
        True if rejection saved
    """
    save_approval(job_id, "REJECTED", {"reason": reason})
    log_activity("REJECTED", job_id, "Unknown", f"Reason: {reason}")
    return True


def route_after_approval(
    state: JobState,
) -> Literal["approved", "rejected", "pending"]:
    """Route based on approval status.

    Args:
        state: Current job state

    Returns:
        Routing decision
    """
    status = state.get("approval_status", "PENDING")

    if status == "APPROVED":
        return "approved"
    elif status == "REJECTED":
        return "rejected"
    else:
        return "pending"


def list_pending_approvals() -> list[dict]:
    """List all pending approval requests.

    Returns:
        List of pending job records
    """
    approvals = load_approvals()
    pending = []

    for job_id, record in approvals.items():
        if record.get("status") == "PENDING":
            pending.append({
                "job_id": job_id,
                **record,
            })

    return pending
