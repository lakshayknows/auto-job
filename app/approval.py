"""
Approval module for email sending gate.
Ensures no email is sent without explicit human approval.

RALPH Approval Guard Prompt:
# ROLE
You are a safety and compliance agent.

# PURPOSE
Ensure no email is sent without explicit human approval.

# RULES
- Block all sending unless approval_status = APPROVED
- Log all decisions
- Never override user consent
"""

import csv
import json
from datetime import datetime, timezone
from typing import Optional

from app.config import Config


class ApprovalManager:
    """
    Approval gate for email sending.
    
    Features:
    - CLI interface for reviewing pending emails
    - Tri-state approval: PENDING, APPROVED, REJECTED
    - Logs all decisions
    - Blocks sending unless explicitly approved
    """

    def __init__(self):
        Config.ensure_directories()

    def _load_approvals(self) -> list[dict]:
        """Load all approval records."""
        if not Config.APPROVALS_JSON.exists():
            return []

        with open(Config.APPROVALS_JSON, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

    def _save_approvals(self, approvals: list[dict]) -> None:
        """Save approvals to JSON and CSV."""
        # Save JSON
        with open(Config.APPROVALS_JSON, "w", encoding="utf-8") as f:
            json.dump(approvals, f, indent=2, ensure_ascii=False)

        # Save CSV
        if approvals:
            fieldnames = sorted(set().union(*[a.keys() for a in approvals]))
            with open(Config.APPROVALS_CSV, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(approvals)

    def list_pending(self) -> list[dict]:
        """Get all pending approval requests."""
        approvals = self._load_approvals()
        return [a for a in approvals if a.get("approval_status") == "PENDING"]

    def list_approved(self) -> list[dict]:
        """Get all approved but unsent emails."""
        approvals = self._load_approvals()
        return [
            a
            for a in approvals
            if a.get("approval_status") == "APPROVED" and not a.get("sent")
        ]

    def list_rejected(self) -> list[dict]:
        """Get all rejected emails."""
        approvals = self._load_approvals()
        return [a for a in approvals if a.get("approval_status") == "REJECTED"]

    def list_sent(self) -> list[dict]:
        """Get all sent emails."""
        approvals = self._load_approvals()
        return [a for a in approvals if a.get("sent")]

    def get_draft(self, draft_id: str) -> Optional[dict]:
        """Get a specific draft by ID."""
        approvals = self._load_approvals()
        for a in approvals:
            if a.get("id") == draft_id:
                return a
        return None

    def approve(self, draft_id: str) -> bool:
        """
        Approve an email draft for sending.
        
        Args:
            draft_id: ID of the draft to approve
            
        Returns:
            True if approved successfully, False otherwise
        """
        approvals = self._load_approvals()

        for approval in approvals:
            if approval.get("id") == draft_id:
                if approval.get("approval_status") != "PENDING":
                    print(
                        f"Draft {draft_id} is not pending "
                        f"(status: {approval.get('approval_status')})"
                    )
                    return False

                approval["approval_status"] = "APPROVED"
                approval["approved_at"] = datetime.now(timezone.utc).isoformat()

                self._save_approvals(approvals)
                print(f"Draft {draft_id} approved.")
                return True

        print(f"Draft {draft_id} not found.")
        return False

    def reject(self, draft_id: str, reason: str = "") -> bool:
        """
        Reject an email draft.
        
        Args:
            draft_id: ID of the draft to reject
            reason: Optional reason for rejection
            
        Returns:
            True if rejected successfully, False otherwise
        """
        approvals = self._load_approvals()

        for approval in approvals:
            if approval.get("id") == draft_id:
                if approval.get("approval_status") not in ["PENDING", "APPROVED"]:
                    print(f"Draft {draft_id} is already rejected.")
                    return False

                approval["approval_status"] = "REJECTED"
                approval["rejection_reason"] = reason
                approval["rejected_at"] = datetime.now(timezone.utc).isoformat()

                self._save_approvals(approvals)
                print(f"Draft {draft_id} rejected.")
                return True

        print(f"Draft {draft_id} not found.")
        return False

    def is_approved(self, draft_id: str) -> bool:
        """Check if a draft is approved for sending."""
        draft = self.get_draft(draft_id)
        if draft:
            return (
                draft.get("approval_status") == "APPROVED" and not draft.get("sent")
            )
        return False

    def mark_sent(self, draft_id: str) -> bool:
        """Mark a draft as sent."""
        approvals = self._load_approvals()

        for approval in approvals:
            if approval.get("id") == draft_id:
                approval["sent"] = True
                approval["sent_at"] = datetime.now(timezone.utc).isoformat()

                self._save_approvals(approvals)
                print(f"Draft {draft_id} marked as sent.")
                return True

        return False

    def interactive_review(self) -> None:
        """
        Interactive CLI for reviewing pending emails.
        Displays each draft and prompts for approval/rejection.
        """
        pending = self.list_pending()

        if not pending:
            print("No pending emails to review.")
            return

        print(f"\n{'='*60}")
        print(f"PENDING EMAIL REVIEW ({len(pending)} drafts)")
        print(f"{'='*60}\n")

        for i, draft in enumerate(pending, 1):
            print(f"\n--- Draft {i}/{len(pending)} ---")
            print(f"ID: {draft.get('id')}")
            print(f"Company: {draft.get('company')}")
            print(f"Role: {draft.get('role')}")
            print(f"To: {draft.get('to_email')}")
            print(f"Subject: {draft.get('subject')}")
            print(f"\nBody:\n{draft.get('body')}")
            print(f"\nResume: {draft.get('resume_path', 'None')}")
            print(f"{'-'*40}")

            while True:
                choice = input("\n[A]pprove / [R]eject / [S]kip / [Q]uit: ").strip().lower()

                if choice == "a":
                    self.approve(draft["id"])
                    break
                elif choice == "r":
                    reason = input("Rejection reason (optional): ").strip()
                    self.reject(draft["id"], reason)
                    break
                elif choice == "s":
                    print("Skipped.")
                    break
                elif choice == "q":
                    print("Exiting review.")
                    return
                else:
                    print("Invalid choice. Please enter A, R, S, or Q.")

        print("\nReview complete!")
        print(f"Approved: {len(self.list_approved())}")
        print(f"Rejected: {len(self.list_rejected())}")
        print(f"Pending: {len(self.list_pending())}")

    def summary(self) -> dict:
        """Get a summary of all approvals."""
        return {
            "pending": len(self.list_pending()),
            "approved": len(self.list_approved()),
            "rejected": len(self.list_rejected()),
            "sent": len(self.list_sent()),
        }


def main():
    """Entry point for approval module."""
    manager = ApprovalManager()

    print("\n=== APPROVAL SUMMARY ===")
    summary = manager.summary()
    for status, count in summary.items():
        print(f"{status.title()}: {count}")

    if manager.list_pending():
        print("\nStarting interactive review...")
        manager.interactive_review()


if __name__ == "__main__":
    main()
