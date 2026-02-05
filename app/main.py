"""CLI entrypoint for AutoJob Agent.

Provides command-line interface for:
- Discovering jobs
- Processing job applications
- Approving/rejecting pending applications
- Viewing status
"""

import argparse
import json
import sys
from pathlib import Path

from app.config import DATA_DIR, get_config, get_logger, setup_logging
from app.graph import get_app
from app.nodes.approval import approve_job, list_pending_approvals, reject_job
from app.state import create_initial_state

logger = get_logger("main")


def load_jobs() -> list[dict]:
    """Load discovered jobs from file.

    Returns:
        List of job dictionaries
    """
    jobs_file = DATA_DIR / "jobs.json"
    if jobs_file.exists():
        with open(jobs_file, "r") as f:
            return json.load(f)
    return []


def cmd_discover(args):
    """Discover jobs from legal sources."""
    logger.info("Starting job discovery...")

    app = get_app()
    config = {"configurable": {"thread_id": "discovery"}}

    # Run scraper node only
    initial_state = {
        "job_id": "",
        "job_data": {},
        "errors": [],
        "llm_calls": 0,
        "total_tokens": 0,
    }

    # The scraper will save jobs to jobs.json
    from app.nodes.scraper import scrape_jobs

    result = scrape_jobs(initial_state)

    jobs = load_jobs()
    print(f"\nDiscovered {len(jobs)} jobs")

    for i, job in enumerate(jobs[:10], 1):
        email_status = "✓" if job.get("contact_email") else "✗"
        print(f"  {i}. [{email_status}] {job.get('company')} - {job.get('role')}")

    if len(jobs) > 10:
        print(f"  ... and {len(jobs) - 10} more")


def find_job_by_id(jobs: list[dict], job_id: str) -> dict | None:
    """Find job by full or partial ID.

    Args:
        jobs: List of job dictionaries
        job_id: Full or partial job ID

    Returns:
        Job dict or None
    """
    # Try exact match first
    job = next((j for j in jobs if j["id"] == job_id), None)
    if job:
        return job

    # Try partial match (prefix)
    job = next((j for j in jobs if j["id"].startswith(job_id)), None)
    return job


def cmd_process(args):
    """Process a specific job application."""
    job_id = args.job_id
    logger.info(f"Processing job: {job_id}")

    # Load jobs
    jobs = load_jobs()
    job = find_job_by_id(jobs, job_id)

    if not job:
        print(f"Job not found: {job_id}")
        return 1

    # Create initial state
    state = create_initial_state(job_id, job)

    # Get graph and run
    app = get_app()
    config = {"configurable": {"thread_id": job_id}}

    print(f"\nProcessing: {job.get('company')} - {job.get('role')}")
    print(f"Contact: {job.get('contact_email', 'N/A')}")
    print("-" * 50)

    # Run graph until interrupt or completion
    for event in app.stream(state, config):
        if isinstance(event, tuple):
            # Some versions return (node, output) tuple
            # If output is a dict, we can get status/errors
            node, output = event
            if isinstance(output, dict):
                status = output.get("approval_status", "N/A")
                errors = output.get("errors", [])
                print(f"  [{node}] status={status}, errors={len(errors)}")
            else:
                print(f"  [{node}] done")
        elif isinstance(event, dict):
            # Others return dict {node: output}
            for node, output in event.items():
                if node == "__end__":
                    continue
                if isinstance(output, dict):
                    status = output.get("approval_status", "N/A")
                    errors = output.get("errors", [])
                    print(f"  [{node}] status={status}, errors={len(errors)}")
                else:
                    print(f"  [{node}] done")

    # Get final state
    final_state = app.get_state(config)
    print("-" * 50)

    if final_state.values.get("approval_status") == "PENDING":
        print("\n⏸️  Waiting for approval. Use 'approve' or 'reject' command.")
    elif final_state.values.get("sent"):
        print("\n✅ Email sent successfully!")
    elif final_state.values.get("errors"):
        print(f"\n❌ Errors: {final_state.values['errors']}")


def cmd_approve(args):
    """Approve a pending job application."""
    job_id = args.job_id
    notes = args.notes or ""

    if approve_job(job_id, notes):
        print(f"✅ Approved: {job_id}")

        # Resume processing
        if args.resume:
            args.job_id = job_id
            cmd_process(args)
    else:
        print(f"❌ Failed to approve: {job_id}")


def cmd_reject(args):
    """Reject a pending job application."""
    job_id = args.job_id
    reason = args.reason or ""

    if reject_job(job_id, reason):
        print(f"❌ Rejected: {job_id}")
    else:
        print(f"Failed to reject: {job_id}")


def cmd_pending(args):
    """List pending approval requests."""
    pending = list_pending_approvals()

    if not pending:
        print("No pending approvals")
        return

    print(f"\nPending Approvals ({len(pending)}):")
    print("-" * 50)

    jobs = load_jobs()
    for record in pending:
        job_id = record["job_id"]
        job = next((j for j in jobs if j["id"] == job_id), {})
        company = job.get("company", "Unknown")
        role = job.get("role", "Unknown")
        print(f"  {job_id[:8]}... | {company} - {role}")


def cmd_status(args):
    """Show overall status."""
    config = get_config()
    jobs = load_jobs()
    pending = list_pending_approvals()

    # Load sent emails
    sent_file = DATA_DIR / "sent_emails.json"
    sent_count = 0
    if sent_file.exists():
        with open(sent_file, "r") as f:
            sent_count = len(json.load(f))

    # Load archive
    archive_file = DATA_DIR / "archive.json"
    archive_count = 0
    if archive_file.exists():
        with open(archive_file, "r") as f:
            archive_count = len(json.load(f))

    print("\n" + "=" * 50)
    print("AutoJob Agent Status")
    print("=" * 50)
    print(f"  CRON_MODE: {'🔴 Active' if config.cron_mode else '🟢 Inactive'}")
    print(f"  Jobs Discovered: {len(jobs)}")
    print(f"  Pending Approvals: {len(pending)}")
    print(f"  Emails Sent: {sent_count}")
    print(f"  Archived: {archive_count}")
    print("=" * 50)


def cmd_list(args):
    """List discovered jobs."""
    jobs = load_jobs()

    if not jobs:
        print("No jobs discovered. Run 'discover' first.")
        return

    print(f"\nDiscovered Jobs ({len(jobs)}):")
    print("-" * 70)
    print(f"{'ID':<10} {'Company':<20} {'Role':<25} {'Email':<15}")
    print("-" * 70)

    for job in jobs[: args.limit]:
        job_id = job["id"][:8]
        company = job.get("company", "")[:18]
        role = job.get("role", "")[:23]
        email = "✓" if job.get("contact_email") else "✗"
        print(f"{job_id:<10} {company:<20} {role:<25} {email:<15}")

    if len(jobs) > args.limit:
        print(f"\n... and {len(jobs) - args.limit} more (use --limit to see more)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AutoJob Agent - Automated Job Application System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Discover command
    discover_parser = subparsers.add_parser(
        "discover",
        help="Discover jobs from legal sources",
    )

    # List command
    list_parser = subparsers.add_parser(
        "list",
        help="List discovered jobs",
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max jobs to display",
    )

    # Process command
    process_parser = subparsers.add_parser(
        "process",
        help="Process a job application",
    )
    process_parser.add_argument(
        "job_id",
        help="Job ID to process",
    )

    # Approve command
    approve_parser = subparsers.add_parser(
        "approve",
        help="Approve a pending application",
    )
    approve_parser.add_argument(
        "job_id",
        help="Job ID to approve",
    )
    approve_parser.add_argument(
        "--notes",
        help="Approval notes",
    )
    approve_parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume processing after approval",
    )

    # Reject command
    reject_parser = subparsers.add_parser(
        "reject",
        help="Reject a pending application",
    )
    reject_parser.add_argument(
        "job_id",
        help="Job ID to reject",
    )
    reject_parser.add_argument(
        "--reason",
        help="Rejection reason",
    )

    # Pending command
    pending_parser = subparsers.add_parser(
        "pending",
        help="List pending approvals",
    )

    # Status command
    status_parser = subparsers.add_parser(
        "status",
        help="Show overall status",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging()

    if args.debug:
        import logging

        logging.getLogger().setLevel(logging.DEBUG)

    # Route to command
    commands = {
        "discover": cmd_discover,
        "list": cmd_list,
        "process": cmd_process,
        "approve": cmd_approve,
        "reject": cmd_reject,
        "pending": cmd_pending,
        "status": cmd_status,
    }

    if args.command in commands:
        try:
            result = commands[args.command](args)
            sys.exit(result or 0)
        except KeyboardInterrupt:
            print("\nInterrupted")
            sys.exit(1)
        except Exception as e:
            logger.exception("Command failed")
            print(f"\n❌ Error: {e}")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
