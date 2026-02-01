"""
Mailer module for sending approved emails via Outlook SMTP.
Implements strict safety gates - only sends after approval.
"""

import smtplib
from email.message import EmailMessage
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from app.approval import ApprovalManager
from app.config import Config


class Mailer:
    """
    Email sender using Outlook SMTP.
    
    CRITICAL SAFETY RULES:
    - NEVER send without approval_status == APPROVED
    - NEVER send if already sent
    - NEVER send in CRON_MODE
    - ALWAYS send one email at a time
    - ALWAYS log all sending attempts
    """

    def __init__(self):
        self.approval_manager = ApprovalManager()

    def _create_message(
        self,
        to_email: str,
        subject: str,
        body: str,
        attachment_path: Optional[Path] = None,
    ) -> MIMEMultipart:
        """Create email message with optional PDF attachment."""
        msg = MIMEMultipart()
        msg["From"] = Config.SMTP_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject

        # Add body
        msg.attach(MIMEText(body, "plain"))

        # Add attachment if provided
        if attachment_path and Path(attachment_path).exists():
            with open(attachment_path, "rb") as f:
                pdf_part = MIMEApplication(f.read(), _subtype="pdf")
                pdf_part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=Path(attachment_path).name,
                )
                msg.attach(pdf_part)

        return msg

    def _check_safety_gates(self, draft_id: str) -> tuple[bool, str]:
        """
        Check all safety gates before sending.
        
        Returns:
            Tuple of (can_send: bool, reason: str)
        """
        # Gate 1: CRON_MODE check
        if Config.CRON_MODE:
            return False, "CRON_MODE is enabled. Manual sending only."

        # Gate 2: Get draft
        draft = self.approval_manager.get_draft(draft_id)
        if not draft:
            return False, f"Draft {draft_id} not found."

        # Gate 3: Approval status
        if draft.get("approval_status") != "APPROVED":
            return (
                False,
                f"Draft not approved (status: {draft.get('approval_status')})",
            )

        # Gate 4: Already sent
        if draft.get("sent"):
            return False, "Email already sent."

        # Gate 5: Missing recipient
        if not draft.get("to_email"):
            return False, "No recipient email address."

        # Gate 6: SMTP credentials
        if not Config.SMTP_PASSWORD:
            return False, "SMTP password not configured in .env"

        return True, "All checks passed."

    def send_email(self, draft_id: str) -> bool:
        """
        Send a single approved email.
        
        Args:
            draft_id: ID of the draft to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        # Check safety gates
        can_send, reason = self._check_safety_gates(draft_id)
        if not can_send:
            print(f"BLOCKED: {reason}")
            return False

        draft = self.approval_manager.get_draft(draft_id)

        print(f"Sending email to {draft['to_email']}...")

        try:
            # Create message
            attachment_path = None
            if draft.get("resume_path"):
                attachment_path = Path(draft["resume_path"])

            msg = self._create_message(
                to_email=draft["to_email"],
                subject=draft["subject"],
                body=draft["body"],
                attachment_path=attachment_path,
            )

            # Send via SMTP
            with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
                server.starttls()
                server.login(Config.SMTP_EMAIL, Config.SMTP_PASSWORD)
                server.send_message(msg)

            # Mark as sent
            self.approval_manager.mark_sent(draft_id)

            print(f"Email sent successfully to {draft['to_email']}")
            return True

        except smtplib.SMTPAuthenticationError:
            print("SMTP authentication failed. Check your credentials.")
            return False
        except smtplib.SMTPException as e:
            print(f"SMTP error: {e}")
            return False
        except Exception as e:
            print(f"Error sending email: {e}")
            return False

    def send_approved(self) -> dict:
        """
        Send all approved but unsent emails.
        Sends one at a time with confirmation.
        
        Returns:
            Summary of sending results
        """
        if Config.CRON_MODE:
            print("CRON_MODE is enabled. Email sending blocked.")
            return {"total": 0, "sent": 0, "failed": 0}

        approved = self.approval_manager.list_approved()

        if not approved:
            print("No approved emails to send.")
            return {"total": 0, "sent": 0, "failed": 0}

        results = {"total": len(approved), "sent": 0, "failed": 0}

        print(f"\n{'='*60}")
        print(f"SENDING APPROVED EMAILS ({len(approved)} pending)")
        print(f"{'='*60}\n")

        for draft in approved:
            print(f"\n--- Sending to: {draft['to_email']} ---")
            print(f"Company: {draft['company']}")
            print(f"Role: {draft['role']}")
            print(f"Subject: {draft['subject']}")

            confirm = input("\nSend this email? [y/N]: ").strip().lower()

            if confirm == "y":
                if self.send_email(draft["id"]):
                    results["sent"] += 1
                else:
                    results["failed"] += 1
            else:
                print("Skipped.")

        print(f"\n{'='*60}")
        print(f"SENDING COMPLETE")
        print(f"Sent: {results['sent']}")
        print(f"Failed: {results['failed']}")
        print(f"{'='*60}")

        return results

    def preview_email(self, draft_id: str) -> None:
        """Preview an email without sending."""
        draft = self.approval_manager.get_draft(draft_id)

        if not draft:
            print(f"Draft {draft_id} not found.")
            return

        print(f"\n{'='*60}")
        print("EMAIL PREVIEW")
        print(f"{'='*60}")
        print(f"From: {Config.SMTP_EMAIL}")
        print(f"To: {draft.get('to_email')}")
        print(f"Subject: {draft.get('subject')}")
        print(f"Attachment: {draft.get('resume_path', 'None')}")
        print(f"Status: {draft.get('approval_status')}")
        print(f"{'='*60}")
        print(f"\n{draft.get('body')}")
        print(f"\n{'='*60}")


def main():
    """Entry point for mailer module."""
    mailer = Mailer()

    # Show summary
    summary = mailer.approval_manager.summary()
    print("\n=== EMAIL STATUS ===")
    for status, count in summary.items():
        print(f"{status.title()}: {count}")

    approved = mailer.approval_manager.list_approved()
    if approved:
        print(f"\n{len(approved)} approved emails ready to send.")
        confirm = input("Start sending? [y/N]: ").strip().lower()
        if confirm == "y":
            mailer.send_approved()


if __name__ == "__main__":
    main()
