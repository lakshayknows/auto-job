"""LangGraph workflow definition for job application pipeline.

This module defines the complete graph structure with:
- All processing nodes
- Conditional edges for guards
- Approval interrupt mechanism
- Memory checkpointing for state persistence
- CRON_MODE enforcement (hard circuit breaker)
"""

from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.config import get_logger
from app.nodes.approval import request_approval, route_after_approval
from app.nodes.email import draft_email
from app.nodes.guards import (
    cost_guard,
    is_cron_mode,
    legal_guard,
    route_after_legal_guard,
    route_after_send_guard,
    send_guard,
    source_guard,
)
from app.nodes.rag import retrieve_context
from app.nodes.resume import tailor_resume
from app.nodes.scraper import scrape_jobs
from app.nodes.sender import archive_job, send_email
from app.state import JobState

logger = get_logger("graph")


def should_skip(state: JobState) -> Literal["continue", "skip"]:
    """Check if current job should be skipped.

    Args:
        state: Current job state

    Returns:
        'skip' if should_skip flag is set, 'continue' otherwise
    """
    if state.get("should_skip", False):
        reason = state.get("skip_reason", "Unknown reason")
        logger.info(f"Skipping job: {reason}")
        return "skip"
    return "continue"


def check_cron_mode(state: JobState) -> JobState:
    """Pre-check for CRON_MODE before LLM nodes.

    In CRON_MODE, this sets should_skip=True which routes to archive.
    The individual nodes also have hard circuit breakers (CronModeError)
    as defense in depth.

    Args:
        state: Current job state

    Returns:
        Updated state with skip flag if CRON_MODE active
    """
    if is_cron_mode():
        logger.info("CRON_MODE active - blocking LLM operations")
        return {
            **state,
            "should_skip": True,
            "skip_reason": "CRON_MODE active - LLM blocked",
        }
    # Only check cost limits when NOT in CRON_MODE
    return cost_guard(state)


def create_graph() -> StateGraph:
    """Create the LangGraph workflow.

    Returns:
        Configured StateGraph instance
    """
    # Initialize graph with state schema
    workflow = StateGraph(JobState)

    # Add nodes
    workflow.add_node("scraper", scrape_jobs)
    workflow.add_node("legal_guard", legal_guard)
    workflow.add_node("source_guard", source_guard)
    workflow.add_node("cron_check", check_cron_mode)
    workflow.add_node("rag", retrieve_context)
    workflow.add_node("resume", tailor_resume)
    workflow.add_node("email", draft_email)
    workflow.add_node("approval", request_approval)
    workflow.add_node("send_guard", send_guard)
    workflow.add_node("sender", send_email)
    workflow.add_node("archive", archive_job)

    # Define edges

    # Start with scraper
    workflow.set_entry_point("scraper")

    # Scraper -> Legal Guard (with skip check)
    workflow.add_conditional_edges(
        "scraper",
        should_skip,
        {
            "continue": "legal_guard",
            "skip": "archive",
        },
    )

    # Legal Guard -> Source Guard or Archive
    workflow.add_conditional_edges(
        "legal_guard",
        route_after_legal_guard,
        {
            "pass": "source_guard",
            "fail": "archive",
        },
    )

    # Source Guard -> CRON Check
    workflow.add_edge("source_guard", "cron_check")

    # CRON Check -> RAG or Archive
    workflow.add_conditional_edges(
        "cron_check",
        should_skip,
        {
            "continue": "rag",
            "skip": "archive",
        },
    )

    # RAG -> Resume
    workflow.add_edge("rag", "resume")

    # Resume -> Email
    workflow.add_edge("resume", "email")

    # Email -> Approval
    workflow.add_edge("email", "approval")

    # Approval -> Send Guard, Archive, or END (pending)
    workflow.add_conditional_edges(
        "approval",
        route_after_approval,
        {
            "approved": "send_guard",
            "rejected": "archive",
            "pending": END,  # Interrupt point - wait for human
        },
    )

    # Send Guard -> Sender or Archive
    workflow.add_conditional_edges(
        "send_guard",
        route_after_send_guard,
        {
            "pass": "sender",
            "fail": "archive",
        },
    )

    # Sender -> Archive
    workflow.add_edge("sender", "archive")

    # Archive -> END
    workflow.add_edge("archive", END)

    return workflow


def compile_graph(checkpointer=None):
    """Compile the graph with optional checkpointer.

    Args:
        checkpointer: Optional checkpointer for state persistence

    Returns:
        Compiled graph application
    """
    workflow = create_graph()

    if checkpointer is None:
        checkpointer = MemorySaver()

    # Compile with interrupt before approval
    app = workflow.compile(
        checkpointer=checkpointer,
    )

    logger.info("Graph compiled successfully")
    return app


def get_graph():
    """Get a compiled graph instance.

    Returns:
        Compiled graph application
    """
    return compile_graph()


# Pre-compiled graph for CLI usage
_graph = None


def get_app():
    """Get the singleton graph application.

    Returns:
        Compiled graph application
    """
    global _graph
    if _graph is None:
        _graph = compile_graph()
    return _graph
