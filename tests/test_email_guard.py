"""Tests for email guard (send guard)."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.nodes.guards import send_guard
from app.state import JobState


class TestSendGuard:
    """Test send guard validation."""

    @pytest.fixture
    def approved_state(self, sample_state) -> JobState:
        """Create an approved state for testing."""
        return {
            **sample_state,
            "approval_status": "APPROVED",
            "resume_pdf_path": str(Path(__file__).parent / "test_resume.pdf"),
            "sent": False,
        }

    def test_send_guard_blocks_unapproved(self, sample_state):
        """Test that unapproved emails are blocked."""
        state = {**sample_state, "approval_status": "PENDING"}
        result = send_guard(state)
        assert result["send_guard_passed"] is False
        assert any("Not approved" in e for e in result.get("errors", []))

    def test_send_guard_blocks_no_email(self, sample_state):
        """Test that missing email blocks sending."""
        state = {
            **sample_state,
            "approval_status": "APPROVED",
            "contact_email": None,
        }
        result = send_guard(state)
        assert result["send_guard_passed"] is False
        assert any("No contact email" in e for e in result.get("errors", []))

    def test_send_guard_blocks_missing_pdf(self, sample_state):
        """Test that missing PDF blocks sending."""
        state = {
            **sample_state,
            "approval_status": "APPROVED",
            "resume_pdf_path": "/nonexistent/path.pdf",
        }
        result = send_guard(state)
        assert result["send_guard_passed"] is False
        assert any("PDF missing" in e for e in result.get("errors", []))

    def test_send_guard_blocks_already_sent(self, sample_state):
        """Test that already sent emails are blocked."""
        state = {
            **sample_state,
            "approval_status": "APPROVED",
            "sent": True,
        }
        result = send_guard(state)
        assert result["send_guard_passed"] is False
        assert any("already sent" in e for e in result.get("errors", []))

    @patch("app.nodes.guards.get_config")
    def test_send_guard_blocks_cron_mode(self, mock_config, sample_state):
        """Test that CRON_MODE blocks sending."""
        mock_cfg = type(
            "Config",
            (),
            {
                "cron_mode": True,
                "cost": type(
                    "Cost",
                    (),
                    {
                        "max_llm_calls_per_run": 25,
                        "max_tokens_per_run": 100000,
                    },
                )(),
            },
        )()
        mock_config.return_value = mock_cfg

        state = {
            **sample_state,
            "approval_status": "APPROVED",
            "resume_pdf_path": __file__,  # Use this test file as "PDF"
            "sent": False,
        }
        result = send_guard(state)
        assert result["send_guard_passed"] is False
        assert any("CRON_MODE" in e for e in result.get("errors", []))

    @patch("app.nodes.guards.get_config")
    def test_send_guard_passes_valid(self, mock_config, sample_state):
        """Test that valid state passes all checks."""
        mock_cfg = type(
            "Config",
            (),
            {
                "cron_mode": False,
                "cost": type(
                    "Cost",
                    (),
                    {
                        "max_llm_calls_per_run": 25,
                        "max_tokens_per_run": 100000,
                    },
                )(),
            },
        )()
        mock_config.return_value = mock_cfg

        state = {
            **sample_state,
            "approval_status": "APPROVED",
            "resume_pdf_path": __file__,  # Use this test file as "PDF"
            "sent": False,
        }
        result = send_guard(state)
        assert result["send_guard_passed"] is True
