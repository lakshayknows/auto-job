"""
Main orchestrator for the job automation system.
Provides CLI commands for all operations.
"""

import argparse
import sys

from app.approval import ApprovalManager
from app.config import Config, llm_counter
from app.email_generator import EmailGenerator
from app.mailer import Mailer
from app.rag import RAGManager
from app.resume_builder import ResumeBuilder
from app.scraper import JobScraper


def cmd_scrape(args) -> None:
    """Run the job scraper."""
    print("\n=== JOB SCRAPER ===\n")

    scraper = JobScraper()
    scraper.run(
        greenhouse_boards=args.greenhouse if args.greenhouse else None,
        lever_boards=args.lever if args.lever else None,
    )


def cmd_index(args) -> None:
    """Build or update RAG index."""
    if Config.CRON_MODE:
        print("CRON_MODE is enabled. RAG indexing skipped.")
        return

    print("\n=== RAG INDEX ===\n")

    rag = RAGManager()
    result = rag.build_index()

    print(f"\nIndexing results:")
    print(f"  Jobs indexed: {result['jobs_indexed']}")
    print(f"  Resume indexed: {result['resume_indexed']}")


def cmd_generate(args) -> None:
    """Generate tailored resumes and email drafts."""
    if Config.CRON_MODE:
        print("CRON_MODE is enabled. Generation skipped.")
        return

    print("\n=== CONTENT GENERATION ===\n")

    # First, ensure RAG index is built
    print("Checking RAG index...")
    rag = RAGManager()
    rag.build_index()

    # Generate resumes
    print("\n--- RESUMES ---")
    resume_builder = ResumeBuilder()
    resume_results = resume_builder.tailor_all_resumes(force=args.force)

    print(f"\nResume results:")
    print(f"  Total: {resume_results['total']}")
    print(f"  Generated: {resume_results['success']}")
    print(f"  Cached: {resume_results['cached']}")
    print(f"  Failed: {resume_results['failed']}")

    # Check LLM limit before continuing
    if not llm_counter.can_call():
        print("\nLLM call limit reached. Email generation skipped.")
        return

    # Generate email drafts
    print("\n--- EMAILS ---")
    email_generator = EmailGenerator()
    email_results = email_generator.generate_all_emails(force=args.force)

    print(f"\nEmail results:")
    print(f"  Total: {email_results['total']}")
    print(f"  Generated: {email_results['success']}")
    print(f"  Cached: {email_results['cached']}")
    print(f"  Failed: {email_results['failed']}")

    print(f"\nLLM calls used: {llm_counter.count}/{llm_counter.max_calls}")


def cmd_review(args) -> None:
    """Interactive approval review."""
    print("\n=== APPROVAL REVIEW ===\n")

    approval_manager = ApprovalManager()

    # Show summary
    summary = approval_manager.summary()
    print("Current status:")
    for status, count in summary.items():
        print(f"  {status.title()}: {count}")

    if args.list:
        # Just list pending
        pending = approval_manager.list_pending()
        if pending:
            print(f"\nPending drafts ({len(pending)}):")
            for draft in pending:
                print(f"  - {draft['id'][:8]}... | {draft['company']} | {draft['role']}")
        return

    if args.approve:
        approval_manager.approve(args.approve)
        return

    if args.reject:
        reason = args.reason if args.reason else ""
        approval_manager.reject(args.reject, reason)
        return

    # Interactive review
    if approval_manager.list_pending():
        approval_manager.interactive_review()
    else:
        print("\nNo pending emails to review.")


def cmd_send(args) -> None:
    """Send approved emails."""
    if Config.CRON_MODE:
        print("CRON_MODE is enabled. Email sending blocked.")
        return

    print("\n=== EMAIL SENDING ===\n")

    mailer = Mailer()

    if args.id:
        # Send specific email
        mailer.send_email(args.id)
    else:
        # Send all approved
        mailer.send_approved()


def cmd_status(args) -> None:
    """Show system status."""
    print("\n=== SYSTEM STATUS ===\n")

    # Config status
    print("Configuration:")
    print(f"  CRON_MODE: {Config.CRON_MODE}")
    print(f"  MAX_LLM_CALLS: {Config.MAX_LLM_CALLS_PER_RUN}")
    print(f"  Google API Key: {'Set' if Config.GOOGLE_API_KEY else 'NOT SET'}")
    print(f"  SMTP Password: {'Set' if Config.SMTP_PASSWORD else 'NOT SET'}")

    # Data status
    print("\nData files:")
    print(f"  jobs.json: {'Exists' if Config.JOBS_JSON.exists() else 'Not found'}")
    print(f"  contacts.json: {'Exists' if Config.CONTACTS_JSON.exists() else 'Not found'}")
    print(f"  approvals.json: {'Exists' if Config.APPROVALS_JSON.exists() else 'Not found'}")

    # Count records
    import json

    if Config.JOBS_JSON.exists():
        with open(Config.JOBS_JSON, "r") as f:
            jobs = json.load(f)
        print(f"  Jobs count: {len(jobs)}")

    if Config.CONTACTS_JSON.exists():
        with open(Config.CONTACTS_JSON, "r") as f:
            contacts = json.load(f)
        print(f"  Contacts count: {len(contacts)}")

    # Approval status
    approval_manager = ApprovalManager()
    summary = approval_manager.summary()
    print("\nApproval status:")
    for status, count in summary.items():
        print(f"  {status.title()}: {count}")

    # Resume status
    compiled_resumes = list(Config.COMPILED_RESUME_DIR.glob("*.pdf"))
    print(f"\nCompiled resumes: {len(compiled_resumes)}")


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Job Automation System - Legal & Approval-Gated",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m app.main scrape                    # Scrape jobs from RemoteOK
  python -m app.main scrape --greenhouse figma # Scrape Greenhouse board
  python -m app.main index                     # Build RAG index
  python -m app.main generate                  # Generate resumes & emails
  python -m app.main review                    # Interactive approval
  python -m app.main send                      # Send approved emails
  python -m app.main status                    # Show system status
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape job listings")
    scrape_parser.add_argument(
        "--greenhouse",
        nargs="*",
        help="Greenhouse board IDs to scrape (e.g., figma stripe)",
    )
    scrape_parser.add_argument(
        "--lever", nargs="*", help="Lever company slugs to scrape"
    )

    # Index command
    subparsers.add_parser("index", help="Build/update RAG index")

    # Generate command
    generate_parser = subparsers.add_parser(
        "generate", help="Generate resumes and emails"
    )
    generate_parser.add_argument(
        "--force", action="store_true", help="Force regeneration of cached items"
    )

    # Review command
    review_parser = subparsers.add_parser("review", help="Review and approve emails")
    review_parser.add_argument(
        "--list", action="store_true", help="List pending drafts only"
    )
    review_parser.add_argument("--approve", help="Approve a specific draft ID")
    review_parser.add_argument("--reject", help="Reject a specific draft ID")
    review_parser.add_argument("--reason", help="Rejection reason")

    # Send command
    send_parser = subparsers.add_parser("send", help="Send approved emails")
    send_parser.add_argument("--id", help="Send a specific draft ID")

    # Status command
    subparsers.add_parser("status", help="Show system status")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Ensure directories exist
    Config.ensure_directories()

    # Route to appropriate command
    commands = {
        "scrape": cmd_scrape,
        "index": cmd_index,
        "generate": cmd_generate,
        "review": cmd_review,
        "send": cmd_send,
        "status": cmd_status,
    }

    try:
        commands[args.command](args)
    except KeyboardInterrupt:
        print("\n\nOperation cancelled.")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
