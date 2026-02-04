"""Email sender node.

Sends approved emails via SMTP and archives completed applications.
"""

import json
import smtplib
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.config import DATA_DIR, get_config, get_logger
from app.state import JobState

logger = get_logger("sender")

# Archive file path
ARCHIVE_FILE = DATA_DIR / "archive.json"
SENT_LOG_FILE = DATA_DIR / "sent_emails.json"


def load_sent_emails() -> dict:
    """Load sent emails log.

    Returns:
        Dict of job_id -> sent record
    """
    if SENT_LOG_FILE.exists():
        with open(SENT_LOG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_sent_email(job_id: str, recipient: str, subject: str):
    """Log sent email.

    Args:
        job_id: Job identifier
        recipient: Email recipient
        subject: Email subject
    """
    sent_emails = load_sent_emails()

    sent_emails[job_id] = {
        "recipient": recipient,
        "subject": subject,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }

    SENT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SENT_LOG_FILE, "w") as f:
        json.dump(sent_emails, f, indent=2)

    logger.info(f"Logged sent email: {job_id} -> {recipient}")


def send_email(state: JobState) -> JobState:
    """LangGraph node: Send approved email via SMTP.

    Args:
        state: Current job state with approved email

    Returns:
        Updated state with sent flag
    """
    config = get_config()

    # Final safety checks
    if config.cron_mode:
        logger.warning("CRON_MODE active - sending blocked")
        return {
            **state,
            "errors": state.get("errors", []) + ["CRON_MODE blocked send"],
        }

    if state.get("approval_status") != "APPROVED":
        logger.error("Attempted to send unapproved email")
        return {
            **state,
            "errors": state.get("errors", []) + ["Cannot send unapproved email"],
        }

    if state.get("sent", False):
        logger.warning("Email already sent - skipping")
        return state

    job_id = state.get("job_id", "unknown")
    recipient = state.get("contact_email")
    subject = state.get("email_subject", "Job Application")
    body = state.get("email_draft", "")
    resume_pdf = state.get("resume_pdf_path")

    if not recipient:
        logger.error("No recipient email")
        return {
            **state,
            "errors": state.get("errors", []) + ["No recipient email"],
        }

    if not config.smtp.email or not config.smtp.password:
        logger.error("SMTP credentials not configured")
        return {
            **state,
            "errors": state.get("errors", []) + ["SMTP not configured"],
        }

    try:
        # Create message
        msg = MIMEMultipart()
        msg["From"] = config.smtp.email
        msg["To"] = recipient
        msg["Subject"] = subject

        # Add body
        msg.attach(MIMEText(body, "plain"))

        # Attach resume PDF if available
        if resume_pdf and Path(resume_pdf).exists():
            with open(resume_pdf, "rb") as f:
                pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
                pdf_attachment.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename="resume.pdf",
                )
                msg.attach(pdf_attachment)

        # Send email
        logger.info(f"Connecting to SMTP: {config.smtp.server}:{config.smtp.port}")

        with smtplib.SMTP(config.smtp.server, config.smtp.port) as server:
            if config.smtp.use_tls:
                server.starttls()
            server.login(config.smtp.email, config.smtp.password)
            server.send_message(msg)

        logger.info(f"Email sent successfully: {job_id} -> {recipient}")

        # Log sent email
        save_sent_email(job_id, recipient, subject)

        return {
            **state,
            "sent": True,
        }

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        return {
            **state,
            "errors": state.get("errors", []) + ["SMTP auth failed"],
        }
    except Exception as e:
        logger.exception("Email sending failed")
        return {
            **state,
            "errors": state.get("errors", []) + [f"Send error: {e}"],
        }


def archive_job(state: JobState) -> JobState:
    """LangGraph node: Archive completed job application.

    Args:
        state: Final job state

    Returns:
        Unchanged state (terminal node)
    """
    job_id = state.get("job_id", "unknown")

    # Load existing archive
    archive = {}
    if ARCHIVE_FILE.exists():
        with open(ARCHIVE_FILE, "r") as f:
            archive = json.load(f)

    # Add job to archive
    archive[job_id] = {
        "job_data": state.get("job_data", {}),
        "approval_status": state.get("approval_status"),
        "sent": state.get("sent", False),
        "errors": state.get("errors", []),
        "archived_at": datetime.now(timezone.utc).isoformat(),
    }

    # Save archive
    ARCHIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ARCHIVE_FILE, "w") as f:
        json.dump(archive, f, indent=2)

    status = "SENT" if state.get("sent") else state.get("approval_status", "UNKNOWN")
    logger.info(f"Archived job {job_id}: {status}")

    return state
