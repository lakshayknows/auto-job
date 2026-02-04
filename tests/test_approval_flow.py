"""Tests for approval flow."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.nodes.approval import (
    approve_job,
    get_approval_status,
    reject_job,
    request_approval,
    route_after_approval,
)
from app.state import JobState


class TestApprovalFlow:
    """Test approval workflow."""

    @pytest.fixture
    def temp_approvals_file(self):
        """Create temporary approvals file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({}, f)
            return Path(f.name)

    def test_request_approval_sets_pending(self, sample_state):
        """Test that request_approval sets status to PENDING."""
        state = {**sample_state, "approval_status": None}
        result = request_approval(state)
        assert result["approval_status"] == "PENDING"

    def test_route_pending(self, sample_state):
        """Test routing for PENDING status."""
        state = {**sample_state, "approval_status": "PENDING"}
        result = route_after_approval(state)
        assert result == "pending"

    def test_route_approved(self, sample_state):
        """Test routing for APPROVED status."""
        state = {**sample_state, "approval_status": "APPROVED"}
        result = route_after_approval(state)
        assert result == "approved"

    def test_route_rejected(self, sample_state):
        """Test routing for REJECTED status."""
        state = {**sample_state, "approval_status": "REJECTED"}
        result = route_after_approval(state)
        assert result == "rejected"

    @patch("app.nodes.approval.APPROVALS_FILE")
    def test_approve_job(self, mock_file, temp_approvals_file):
        """Test approving a job."""
        mock_file.__str__ = lambda x: str(temp_approvals_file)
        mock_file.exists.return_value = True
        mock_file.parent.mkdir = lambda **kwargs: None

        # Mock the file operations
        with patch("app.nodes.approval.load_approvals", return_value={}):
            with patch("builtins.open", create=True):
                result = approve_job("test-123", "Looks good")
                assert result is True

    @patch("app.nodes.approval.APPROVALS_FILE")
    def test_reject_job(self, mock_file, temp_approvals_file):
        """Test rejecting a job."""
        mock_file.__str__ = lambda x: str(temp_approvals_file)
        mock_file.exists.return_value = True
        mock_file.parent.mkdir = lambda **kwargs: None

        with patch("app.nodes.approval.load_approvals", return_value={}):
            with patch("builtins.open", create=True):
                result = reject_job("test-123", "Not a good fit")
                assert result is True

    def test_existing_approval_used(self, sample_state):
        """Test that existing approval is reused."""
        with patch(
            "app.nodes.approval.get_approval_status",
            return_value="APPROVED"
        ):
            state = {**sample_state, "approval_status": "PENDING"}
            result = request_approval(state)
            assert result["approval_status"] == "APPROVED"


class TestApprovalGate:
    """Test that approval gate blocks unapproved emails."""

    def test_graph_stops_at_pending(self, sample_state):
        """Test that graph stops at PENDING status."""
        state = {**sample_state, "approval_status": "PENDING"}
        route = route_after_approval(state)
        assert route == "pending"

    def test_approved_proceeds_to_send(self, sample_state):
        """Test that APPROVED proceeds to send guard."""
        state = {**sample_state, "approval_status": "APPROVED"}
        route = route_after_approval(state)
        assert route == "approved"

    def test_rejected_goes_to_archive(self, sample_state):
        """Test that REJECTED goes to archive."""
        state = {**sample_state, "approval_status": "REJECTED"}
        route = route_after_approval(state)
        assert route == "rejected"
