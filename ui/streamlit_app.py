"""Streamlit UI for AutoJob Agent testing.

This is for local testing only and is not committed to the repository.
"""

import json
import sys
from pathlib import Path

import streamlit as st

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import DATA_DIR, get_config, setup_logging
from app.nodes.approval import approve_job, list_pending_approvals, reject_job
from app.state import create_initial_state

# Setup
setup_logging()

st.set_page_config(
    page_title="AutoJob Agent",
    page_icon="📧",
    layout="wide",
)

st.title("📧 AutoJob Agent")
st.markdown("*LangGraph-powered job application automation*")


def load_jobs():
    """Load discovered jobs."""
    jobs_file = DATA_DIR / "jobs.json"
    if jobs_file.exists():
        with open(jobs_file, "r") as f:
            return json.load(f)
    return []


def load_archive():
    """Load archived jobs."""
    archive_file = DATA_DIR / "archive.json"
    if archive_file.exists():
        with open(archive_file, "r") as f:
            return json.load(f)
    return {}


def load_sent():
    """Load sent emails."""
    sent_file = DATA_DIR / "sent_emails.json"
    if sent_file.exists():
        with open(sent_file, "r") as f:
            return json.load(f)
    return {}


# Sidebar - Status
with st.sidebar:
    st.header("📊 Status")

    config = get_config()
    jobs = load_jobs()
    archive = load_archive()
    sent = load_sent()
    pending = list_pending_approvals()

    cron_status = "🔴 Active" if config.cron_mode else "🟢 Inactive"
    st.metric("CRON_MODE", cron_status)

    col1, col2 = st.columns(2)
    col1.metric("Jobs Found", len(jobs))
    col2.metric("Pending", len(pending))

    col3, col4 = st.columns(2)
    col3.metric("Sent", len(sent))
    col4.metric("Archived", len(archive))

    st.divider()

    # Cost tracking placeholder
    st.header("💰 Cost Tracking")
    st.metric("LLM Calls", "0 / 25")
    st.metric("Tokens Used", "0 / 100K")

# Main tabs
tab1, tab2, tab3, tab4 = st.tabs(
    ["🔍 Jobs", "⏳ Pending Approvals", "📤 Sent", "📁 Archive"]
)

# Jobs tab
with tab1:
    st.header("Discovered Jobs")

    if st.button("🔄 Refresh Jobs"):
        st.rerun()

    if not jobs:
        st.info("No jobs discovered yet. Run `python -m app.main discover` first.")
    else:
        for i, job in enumerate(jobs[:20]):
            with st.expander(
                f"**{job.get('company', 'Unknown')}** - {job.get('role', 'Unknown')}"
            ):
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.write(f"**ID:** `{job['id'][:8]}...`")
                    st.write(f"**Source:** {job.get('source', 'Unknown')}")
                    st.write(f"**Location:** {job.get('location', 'N/A')}")

                    email = job.get("contact_email")
                    if email:
                        st.success(f"**Email:** {email}")
                    else:
                        st.warning("No email found")

                with col2:
                    if st.button("Process", key=f"process_{job['id']}"):
                        st.info(
                            f"Run: `python -m app.main process {job['id']}`"
                        )

                st.write("**Description:**")
                st.text(job.get("description", "")[:500] + "...")

# Pending Approvals tab
with tab2:
    st.header("Pending Approvals")

    if not pending:
        st.info("No pending approvals")
    else:
        for record in pending:
            job_id = record["job_id"]
            job = next((j for j in jobs if j["id"] == job_id), {})

            with st.expander(
                f"**{job.get('company', 'Unknown')}** - {job.get('role', 'Unknown')}"
            ):
                st.write(f"**Job ID:** `{job_id}`")
                st.write(f"**Contact:** {job.get('contact_email', 'N/A')}")

                # Load email draft if exists
                draft_file = DATA_DIR / f"email_draft_{job_id[:8]}.json"
                if draft_file.exists():
                    with open(draft_file) as f:
                        draft = json.load(f)
                    st.write("**Email Draft:**")
                    st.text_area(
                        "Draft",
                        draft.get("body", ""),
                        key=f"draft_{job_id}",
                        disabled=True,
                    )
                    st.write(f"Word count: {draft.get('word_count', 'N/A')}")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Approve", key=f"approve_{job_id}"):
                        approve_job(job_id)
                        st.success("Approved!")
                        st.rerun()

                with col2:
                    if st.button("❌ Reject", key=f"reject_{job_id}"):
                        reject_job(job_id, "Rejected via UI")
                        st.warning("Rejected")
                        st.rerun()

# Sent tab
with tab3:
    st.header("Sent Emails")

    if not sent:
        st.info("No emails sent yet")
    else:
        for job_id, record in sent.items():
            with st.expander(f"**{record.get('recipient', 'Unknown')}**"):
                st.write(f"**Subject:** {record.get('subject', 'N/A')}")
                st.write(f"**Sent:** {record.get('sent_at', 'N/A')}")

# Archive tab
with tab4:
    st.header("Archived Applications")

    if not archive:
        st.info("No archived applications")
    else:
        for job_id, record in archive.items():
            job_data = record.get("job_data", {})
            status = record.get("approval_status", "Unknown")
            sent_status = "✅ Sent" if record.get("sent") else "❌ Not Sent"

            with st.expander(
                f"{job_data.get('company', 'Unknown')} - {status} - {sent_status}"
            ):
                st.write(f"**Job ID:** `{job_id}`")
                st.write(f"**Role:** {job_data.get('role', 'N/A')}")
                st.write(f"**Archived:** {record.get('archived_at', 'N/A')}")

                errors = record.get("errors", [])
                if errors:
                    st.error(f"Errors: {', '.join(errors)}")

# Footer
st.divider()
st.caption("AutoJob Agent v2.0 - LangGraph Edition")
