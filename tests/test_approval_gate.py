"""
Test approval gate module.
Verify: cannot send unless APPROVED, rejected never sent, pending blocked.
"""

import json
import pytest
from pathlib import Path

from app.approval import ApprovalManager
from app.config import Config


class TestApprovalGate:
    """Test suite for approval gate."""

    def test_cannot_send_pending(self, tmp_path, monkeypatch):
        """Verify pending emails cannot be sent."""
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text(json.dumps([
            {"id": "draft1", "job_id": "job1", "approval_status": "PENDING", "sent": False}
        ]))
        
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        
        manager = ApprovalManager()
        approved = manager.list_approved()
        
        assert len(approved) == 0, "Pending draft returned as approved"

    def test_cannot_send_rejected(self, tmp_path, monkeypatch):
        """Verify rejected emails cannot be sent."""
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text(json.dumps([
            {"id": "draft1", "job_id": "job1", "approval_status": "REJECTED", "sent": False}
        ]))
        
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        
        manager = ApprovalManager()
        approved = manager.list_approved()
        
        assert len(approved) == 0, "Rejected draft returned as approved"

    def test_approved_can_send(self, tmp_path, monkeypatch):
        """Verify approved emails can be sent."""
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text(json.dumps([
            {"id": "draft1", "job_id": "job1", "approval_status": "APPROVED", "sent": False}
        ]))
        
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        
        manager = ApprovalManager()
        approved = manager.list_approved()
        
        assert len(approved) == 1, "Approved draft not returned"

    def test_already_sent_excluded(self, tmp_path, monkeypatch):
        """Verify already sent emails are excluded."""
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text(json.dumps([
            {"id": "draft1", "job_id": "job1", "approval_status": "APPROVED", "sent": True}
        ]))
        
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        
        manager = ApprovalManager()
        approved = manager.list_approved()
        
        assert len(approved) == 0, "Already sent draft returned"

    def test_approve_updates_status(self, tmp_path, monkeypatch):
        """Verify approve() updates status to APPROVED."""
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text(json.dumps([
            {"id": "draft1", "job_id": "job1", "approval_status": "PENDING", "sent": False}
        ]))
        csv_file = tmp_path / "approvals.csv"
        
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        monkeypatch.setattr(Config, "APPROVALS_CSV", csv_file)
        
        manager = ApprovalManager()
        result = manager.approve("draft1")
        
        assert result is True
        
        # Verify file updated
        with open(approvals_file) as f:
            data = json.load(f)
        assert data[0]["approval_status"] == "APPROVED"

    def test_reject_updates_status(self, tmp_path, monkeypatch):
        """Verify reject() updates status to REJECTED."""
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text(json.dumps([
            {"id": "draft1", "job_id": "job1", "approval_status": "PENDING", "sent": False}
        ]))
        csv_file = tmp_path / "approvals.csv"
        
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        monkeypatch.setattr(Config, "APPROVALS_CSV", csv_file)
        
        manager = ApprovalManager()
        result = manager.reject("draft1", "Not relevant")
        
        assert result is True
        
        # Verify file updated
        with open(approvals_file) as f:
            data = json.load(f)
        assert data[0]["approval_status"] == "REJECTED"

    def test_tri_state_only(self, tmp_path, monkeypatch):
        """Verify only PENDING, APPROVED, REJECTED states exist."""
        valid_states = ["PENDING", "APPROVED", "REJECTED"]
        
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text(json.dumps([
            {"id": "draft1", "approval_status": "PENDING"},
            {"id": "draft2", "approval_status": "APPROVED"},
            {"id": "draft3", "approval_status": "REJECTED"},
        ]))
        
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        
        manager = ApprovalManager()
        approvals = manager._load_approvals()
        
        for approval in approvals:
            assert approval["approval_status"] in valid_states
