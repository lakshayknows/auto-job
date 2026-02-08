"""Comprehensive tests for CRON_MODE enforcement.

CRON_MODE is a hard safety boundary that allows only:
- Job scraping (read-only HTTP)
- Email discovery from public pages (read-only HTTP)
- Writing to jobs.json (local data)
- Logging

CRON_MODE MUST block:
- RAG retrieval
- Resume generation
- Email drafting
- Approval flow
- SMTP sending
- Any LLM invocation

These tests verify the invariants are enforced.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.nodes.guards import (
    CronModeError,
    assert_not_cron_mode,
    cost_guard,
    cron_mode_guard,
    is_cron_mode,
    send_guard,
)


# =============================================================================
# Test: CRON_MODE Detection Helpers
# =============================================================================


class TestCronModeHelpers:
    """Test CRON_MODE detection and assertion helpers."""

    @patch("app.nodes.guards.get_config")
    def test_is_cron_mode_returns_true_when_active(self, mock_config):
        """Test is_cron_mode returns True when CRON_MODE is active."""
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = True
        mock_config.return_value = mock_cfg

        assert is_cron_mode() is True

    @patch("app.nodes.guards.get_config")
    def test_assert_not_cron_mode_raises_when_active(self, mock_config):
        """Test assert_not_cron_mode raises CronModeError when CRON_MODE is active."""
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = True
        mock_config.return_value = mock_cfg

        with pytest.raises(CronModeError) as exc_info:
            assert_not_cron_mode("test operation")

        assert exc_info.value.operation == "test operation"
        assert "CRON_MODE active" in str(exc_info.value)


# =============================================================================
# Test: RAG Node is Blocked in CRON_MODE
# =============================================================================


class TestRAGBlockedInCronMode:
    """Test that RAG retrieval is blocked in CRON_MODE."""

    @patch("app.nodes.guards.get_config")
    def test_rag_raises_cron_mode_error(self, mock_config, sample_state):
        """Test that RAG node raises CronModeError in CRON_MODE."""
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = True
        mock_config.return_value = mock_cfg

        from app.nodes.rag import retrieve_context

        with pytest.raises(CronModeError) as exc_info:
            retrieve_context(sample_state)

        assert exc_info.value.operation == "RAG retrieval"


# =============================================================================
# Test: Resume Generation is Blocked in CRON_MODE
# =============================================================================


class TestResumeBlockedInCronMode:
    """Test that resume generation is blocked in CRON_MODE."""

    @patch("app.nodes.guards.get_config")
    def test_resume_raises_cron_mode_error(self, mock_config, sample_state):
        """Test that resume node raises CronModeError in CRON_MODE."""
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = True
        mock_config.return_value = mock_cfg

        from app.nodes.resume import tailor_resume

        with pytest.raises(CronModeError) as exc_info:
            tailor_resume(sample_state)

        assert exc_info.value.operation == "resume tailoring"


# =============================================================================
# Test: Email Drafting is Blocked in CRON_MODE
# =============================================================================


class TestEmailDraftingBlockedInCronMode:
    """Test that email drafting is blocked in CRON_MODE."""

    @patch("app.nodes.guards.get_config")
    def test_email_raises_cron_mode_error(self, mock_config, sample_state):
        """Test that email node raises CronModeError in CRON_MODE."""
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = True
        mock_config.return_value = mock_cfg

        from app.nodes.email import draft_email

        with pytest.raises(CronModeError) as exc_info:
            draft_email(sample_state)

        assert exc_info.value.operation == "email drafting"


# =============================================================================
# Test: Email Sending is Blocked in CRON_MODE
# =============================================================================


class TestEmailSendingBlockedInCronMode:
    """Test that email sending is blocked in CRON_MODE."""

    @patch("app.nodes.guards.get_config")
    def test_sender_raises_cron_mode_error(self, mock_config, sample_state):
        """Test that sender node raises CronModeError in CRON_MODE."""
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = True
        mock_config.return_value = mock_cfg

        from app.nodes.sender import send_email

        with pytest.raises(CronModeError) as exc_info:
            send_email(sample_state)

        assert exc_info.value.operation == "email sending"


# =============================================================================
# Test: Send Guard Blocks in CRON_MODE
# =============================================================================


class TestSendGuardBlockedInCronMode:
    """Test that send guard fails in CRON_MODE."""

    @patch("app.nodes.guards.get_config")
    def test_send_guard_fails_in_cron_mode(self, mock_config, sample_state):
        """Test that send guard blocks sending in CRON_MODE."""
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = True
        mock_config.return_value = mock_cfg

        state = {
            **sample_state,
            "approval_status": "APPROVED",
            "contact_email": "test@example.com",
            "resume_pdf_path": None,  # Missing, but CRON_MODE should fail first
        }

        result = send_guard(state)
        assert result.get("send_guard_passed") is False
        assert any("CRON_MODE" in err for err in result.get("errors", []))


# =============================================================================
# Test: Cost Guard is Disabled in CRON_MODE
# =============================================================================


class TestCostGuardDisabledInCronMode:
    """Test that cost guard is explicitly disabled in CRON_MODE."""

    @patch("app.nodes.guards.get_config")
    def test_cost_guard_skipped_in_cron_mode(self, mock_config, sample_state):
        """Test that cost guard returns state unchanged in CRON_MODE."""
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = True
        mock_config.return_value = mock_cfg

        state = {
            **sample_state,
            "llm_calls": 1000,  # Way over any limit
            "total_tokens": 10000000,  # Way over any limit
        }

        result = cost_guard(state)
        # Should not add should_skip or errors - cost guard is disabled
        assert result.get("should_skip") is not True
        assert result.get("errors") == sample_state.get("errors", [])


# =============================================================================
# Test: CRON Mode Guard (Soft Skip)
# =============================================================================


class TestCronModeGuard:
    """Test cron_mode_guard function for soft skip behavior."""

    @patch("app.nodes.guards.get_config")
    def test_cron_mode_guard_sets_skip_when_active(self, mock_config, sample_state):
        """Test that cron_mode_guard sets should_skip when CRON_MODE is active."""
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = True
        mock_config.return_value = mock_cfg

        result = cron_mode_guard(sample_state)
        assert result["should_skip"] is True
        assert "CRON_MODE" in result.get("skip_reason", "")


# =============================================================================
# Test: No LLM Calls Made in CRON_MODE
# =============================================================================


class TestNoLLMCallsInCronMode:
    """Test that no LLM calls are made when CRON_MODE is active."""

    @patch("app.nodes.guards.get_config")
    @patch("langchain_google_genai.ChatGoogleGenerativeAI")
    def test_no_llm_instantiated_in_cron_mode_resume(
        self, mock_llm_class, mock_config, sample_state
    ):
        """Test that LLM is never instantiated for resume in CRON_MODE."""
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = True
        mock_config.return_value = mock_cfg

        from app.nodes.resume import tailor_resume

        with pytest.raises(CronModeError):
            tailor_resume(sample_state)

        # LLM should never be instantiated because we raise before reaching it
        mock_llm_class.assert_not_called()

    @patch("app.nodes.guards.get_config")
    @patch("langchain_google_genai.ChatGoogleGenerativeAI")
    def test_no_llm_instantiated_in_cron_mode_email(
        self, mock_llm_class, mock_config, sample_state
    ):
        """Test that LLM is never instantiated for email in CRON_MODE."""
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = True
        mock_config.return_value = mock_cfg

        from app.nodes.email import draft_email

        with pytest.raises(CronModeError):
            draft_email(sample_state)

        # LLM should never be instantiated because we raise before reaching it
        mock_llm_class.assert_not_called()


# =============================================================================
# Test: Scraper Runs in CRON_MODE
# =============================================================================


class TestScraperAllowedInCronMode:
    """Test that scraper runs successfully in CRON_MODE."""

    @patch("app.nodes.guards.get_config")
    def test_scraper_does_not_check_cron_mode(self, mock_config):
        """Test that scraper node does not block on CRON_MODE.

        Scraper is allowed in CRON_MODE because it's read-only HTTP.
        """
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = True
        mock_config.return_value = mock_cfg

        # The scraper module itself does not check CRON_MODE
        # It's allowed to run for job discovery
        from app.nodes.scraper import scrape_jobs

        # scrape_jobs doesn't import or call assert_not_cron_mode
        # This test verifies the design - scraper is intentionally allowed
        import inspect

        source = inspect.getsource(scrape_jobs)
        assert "assert_not_cron_mode" not in source
        assert "CronModeError" not in source


# =============================================================================
# Test: Approval Not Reached in CRON_MODE
# =============================================================================


class TestApprovalNotReachedInCronMode:
    """Test that approval flow is never reached in CRON_MODE.

    In CRON_MODE, the graph should skip from cron_check to archive,
    never reaching the approval node.
    """

    @patch("app.nodes.guards.get_config")
    def test_graph_routes_to_skip_in_cron_mode(self, mock_config, sample_state):
        """Test that check_cron_mode returns skip state."""
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = True
        mock_config.return_value = mock_cfg

        from app.graph import check_cron_mode

        result = check_cron_mode(sample_state)
        assert result["should_skip"] is True
        assert "CRON_MODE active - LLM blocked" in result.get("skip_reason", "")


# =============================================================================
# Test: CLI-Level CRON_MODE Enforcement
# =============================================================================


class TestCLICronModeEnforcement:
    """Test that CLI enforces CRON_MODE command restrictions."""

    def test_cron_allowed_commands_defined(self):
        """Test that CRON_ALLOWED_COMMANDS is properly defined."""
        # Inspect main.py to verify the allowed commands
        import ast
        from pathlib import Path

        main_path = Path(__file__).parent.parent / "app" / "main.py"
        source = main_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        # Look for CRON_ALLOWED_COMMANDS assignment
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "CRON_ALLOWED_COMMANDS":
                        found = True
                        break

        assert found, "CRON_ALLOWED_COMMANDS should be defined in main.py"


# =============================================================================
# Test: CronModeError Exception
# =============================================================================


class TestCronModeErrorException:
    """Test CronModeError exception behavior."""

    def test_cron_mode_error_stores_operation(self):
        """Test that CronModeError stores the blocked operation."""
        error = CronModeError("test operation")
        assert error.operation == "test operation"
        assert "test operation" in str(error)
        assert "CRON_MODE active" in str(error)

    def test_cron_mode_error_is_runtime_error(self):
        """Test that CronModeError is a RuntimeError subclass."""
        error = CronModeError("test")
        assert isinstance(error, RuntimeError)
