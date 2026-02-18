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
import traceback

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

    scrape_jobs(initial_state)

    jobs = load_jobs()
    print(f"\nDiscovered {len(jobs)} jobs")

    for i, job in enumerate(jobs[:10], 1):
        email_status = "✓" if job.get("contact_email") else "✗"
        company = job.get("company")
        role = job.get("role")
        print(f"  {i}. [{email_status}] {company} - {role}")

    if len(jobs) > 10:
        print(f"  ... and {len(jobs) - 10} more")


def cmd_run_all(args):
    """Discover jobs and process each through resume + email (no sending).

    Runs the full pipeline up to the approval gate:
    1. Discover new jobs (scrape)
    2. For each eligible job: RAG → resume → email draft → PENDING
    3. Stops at PENDING — user manually approves and sends later
    """
    dry_run = getattr(args, "dry_run", False)

    # Step 1: Discover jobs
    print("=" * 50)
    print("Step 1: Discovering jobs...")
    print("=" * 50)
    from app.nodes.scraper import scrape_jobs

    initial_state = {
        "job_id": "",
        "job_data": {},
        "errors": [],
        "llm_calls": 0,
        "total_tokens": 0,
    }
    scrape_jobs(initial_state)

    # Step 2: Load jobs and determine which to process
    jobs = load_jobs()
    print(f"\nTotal discovered jobs: {len(jobs)}")

    # Load already-processed data to skip duplicates
    archive_file = DATA_DIR / "archive.json"
    archive = {}
    if archive_file.exists():
        with open(archive_file, "r") as f:
            archive = json.load(f)

    sent_file = DATA_DIR / "sent_emails.json"
    sent = {}
    if sent_file.exists():
        with open(sent_file, "r") as f:
            sent = json.load(f)

    from app.nodes.approval import load_approvals

    approvals = load_approvals()

    eligible = []
    for job in jobs:
        jid = job.get("id", "")
        if not job.get("contact_email"):
            continue
        if jid in archive:
            continue
        if jid in sent:
            continue
        if jid in approvals:
            continue
        eligible.append(job)

    print(f"Eligible jobs to process: {len(eligible)}")

    if not eligible:
        print("\n✅ No new jobs to process.")
        return

    if dry_run:
        print("\n🏃 Dry run — listing eligible jobs only:")
        for i, job in enumerate(eligible, 1):
            company = job.get("company")
            role = job.get("role")
            jid = job["id"][:8]
            print(f"  {i}. {company} — {role} ({jid}...)")
        n = len(eligible)
        print(f"\nRun without --dry-run to process these {n} jobs.")
        return

    # Step 3: Process each eligible job
    print("\n" + "=" * 50)
    print("Step 2: Processing jobs (resume + email draft)...")
    print("=" * 50)

    app = get_app()
    processed = 0
    failed = 0

    for i, job in enumerate(eligible, 1):
        job_id = job["id"]
        company = job.get("company", "Unknown")
        role = job.get("role", "Unknown")
        print(f"\n[{i}/{len(eligible)}] {company} — {role} ({job_id[:8]}...)")

        try:
            state = create_initial_state(job_id, job)
            graph_config = {"configurable": {"thread_id": job_id}}

            for event in app.stream(state, graph_config):
                if isinstance(event, dict):
                    for node, output in event.items():
                        if node != "__end__":
                            print(f"    [{node}] done")

            # Check final state
            final_state = app.get_state(graph_config)
            status = final_state.values.get("approval_status", "UNKNOWN")

            if status == "PENDING":
                short_id = job_id[:8]
                print(f"    📋 PENDING — approve: {short_id}")
                processed += 1
            elif final_state.values.get("errors"):
                print(f"    ❌ Errors: {final_state.values['errors']}")
                failed += 1
            else:
                print(f"    ✓ Status: {status}")
                processed += 1

        except Exception as e:
            print(f"    ❌ Failed: {e}")
            tb = traceback.format_exc()
            logger.error(f"run-all failed for {job_id}: {tb}")
            failed += 1

    # Summary
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"  Processed: {processed}")
    print(f"  Failed:    {failed}")
    print(f"  Skipped:   {len(jobs) - len(eligible)}")
    if processed > 0:
        print("\n📋 Review pending: python -m app.main pending")
        print("   Approve a job:  python -m app.main approve <id>")


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
    graph_config = {"configurable": {"thread_id": job_id}}

    print(f"\nProcessing: {job.get('company')} - {job.get('role')}")
    print(f"Contact: {job.get('contact_email', 'N/A')}")
    print("-" * 50)

    # Run graph until interrupt or completion
    for event in app.stream(state, graph_config):
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
    final_state = app.get_state(graph_config)
    print("-" * 50)

    if final_state.values.get("approval_status") == "PENDING":
        print("\n" + "=" * 50)
        print("📋 APPROVAL REQUIRED")
        print("=" * 50)

        # Show draft for review
        email_draft = final_state.values.get("email_draft", "No draft available")
        email_subject = final_state.values.get("email_subject", "")
        contact = job.get("contact_email", "N/A")

        print(f"\nTo: {contact}")
        print(f"Subject: {email_subject}")
        print(f"\n{'-' * 40}")
        print(email_draft[:600] + ("..." if len(email_draft) > 600 else ""))
        print(f"{'-' * 40}")

        # Interactive approval (only in non-CRON mode)
        app_config = get_config()
        if not app_config.cron_mode:
            try:
                response = input("\nApprove and send? [y/n]: ").strip().lower()
                if response == "y":
                    from app.nodes.approval import approve_job

                    if approve_job(job_id, "Approved via CLI"):
                        print("✅ Approved! Resuming send flow...")
                        # Resume graph processing
                        for event in app.stream(None, graph_config):
                            if isinstance(event, dict):
                                for node, output in event.items():
                                    if node != "__end__":
                                        print(f"  [{node}] done")
                        print("\n✅ Process complete!")
                    else:
                        print("❌ Approval failed")
                else:
                    print("\n⏸️  Not approved." " Run 'approve <job_id>' later.")
            except EOFError:
                # Non-interactive mode (e.g., piped input)
                print("\n⏸️  Interactive approval not available.")
                print(f"   Run: python -m app.main approve {job_id}")
        else:
            print("\n⚠️  CRON_MODE active - interactive approval disabled")
            print(f"   Run: python -m app.main approve {job_id}")
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
        remaining = len(jobs) - args.limit
        print(f"\n... and {remaining} more (use --limit)")


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
    subparsers.add_parser(
        "discover",
        help="Discover jobs from legal sources",
    )

    # Run-all command (discover + resume + email)
    run_all_parser = subparsers.add_parser(
        "run-all",
        help="Discover jobs and generate resume + email for each (no sending)",
    )
    run_all_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List eligible jobs without processing them",
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
    subparsers.add_parser(
        "pending",
        help="List pending approvals",
    )

    # Status command
    subparsers.add_parser(
        "status",
        help="Show overall status",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging()

    if args.debug:
        import logging

        logging.getLogger().setLevel(logging.DEBUG)

    # CRON_MODE enforcement at CLI level
    # Only allow safe, read-only commands when CRON_MODE is active
    config = get_config()
    CRON_ALLOWED_COMMANDS = {"discover", "list", "status"}

    if config.cron_mode and args.command not in CRON_ALLOWED_COMMANDS:
        allowed = ", ".join(CRON_ALLOWED_COMMANDS)
        print(f"❌ CRON_MODE active - only {allowed} allowed")
        print("   Set CRON_MODE=false to enable processing commands")
        sys.exit(1)

    # Route to command
    commands = {
        "discover": cmd_discover,
        "run-all": cmd_run_all,
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
            # Check for CronModeError (defense in depth)
            from app.nodes.guards import CronModeError

            if isinstance(e, CronModeError):
                print(f"\n❌ CRON_MODE blocked operation: {e.operation}")
                print("   This operation is not allowed when CRON_MODE=true")
                sys.exit(1)
            logger.exception("Command failed")
            print(f"\n❌ Error: {e}")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
