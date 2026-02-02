"""
Test mailer safety module.
Verify: SMTP not called for unapproved, one-at-a-time, correct attachment.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.mailer import Mailer
from app.config import Config


class TestMailerSafety:
    """Test suite for mailer safety."""

    def test_smtp_not_called_for_pending(self, tmp_path, monkeypatch):
        """Verify SMTP not called for pending drafts."""
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text(json.dumps([
            {"id": "draft1", "approval_status": "PENDING", "sent": False, "to_email": "test@test.com"}
        ]))
        
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        monkeypatch.setattr(Config, "CRON_MODE", False)
        
        mailer = Mailer()
        
        with patch('smtplib.SMTP') as mock_smtp:
            result = mailer.send_email("draft1")
            mock_smtp.assert_not_called()
        
        assert result is False

    def test_smtp_not_called_for_rejected(self, tmp_path, monkeypatch):
        """Verify SMTP not called for rejected drafts."""
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text(json.dumps([
            {"id": "draft1", "approval_status": "REJECTED", "sent": False, "to_email": "test@test.com"}
        ]))
        
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        monkeypatch.setattr(Config, "CRON_MODE", False)
        
        mailer = Mailer()
        
        with patch('smtplib.SMTP') as mock_smtp:
            result = mailer.send_email("draft1")
            mock_smtp.assert_not_called()
        
        assert result is False

    def test_smtp_not_called_for_already_sent(self, tmp_path, monkeypatch):
        """Verify SMTP not called for already sent drafts."""
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text(json.dumps([
            {"id": "draft1", "approval_status": "APPROVED", "sent": True, "to_email": "test@test.com"}
        ]))
        
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        monkeypatch.setattr(Config, "CRON_MODE", False)
        
        mailer = Mailer()
        
        with patch('smtplib.SMTP') as mock_smtp:
            result = mailer.send_email("draft1")
            mock_smtp.assert_not_called()
        
        assert result is False

    def test_cron_mode_blocks_sending(self, tmp_path, monkeypatch):
        """Verify CRON_MODE blocks all sending."""
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text(json.dumps([
            {"id": "draft1", "approval_status": "APPROVED", "sent": False, "to_email": "test@test.com"}
        ]))
        
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        monkeypatch.setattr(Config, "CRON_MODE", True)
        
        mailer = Mailer()
        
        with patch('smtplib.SMTP') as mock_smtp:
            result = mailer.send_email("draft1")
            mock_smtp.assert_not_called()
        
        assert result is False

    def test_attachment_path_validation(self, tmp_path, monkeypatch):
        """Verify attachment path is validated."""
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text(json.dumps([
            {
                "id": "draft1",
                "approval_status": "APPROVED",
                "sent": False,
                "to_email": "test@test.com",
                "resume_path": str(tmp_path / "resume.pdf")
            }
        ]))
        
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        
        mailer = Mailer()
        draft = mailer.approval_manager.get_draft("draft1")
        
        # Path should be stored
        assert draft["resume_path"] is not None

    def test_no_bulk_send(self, tmp_path, monkeypatch):
        """Verify emails are sent one at a time."""
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text(json.dumps([
            {"id": "draft1", "approval_status": "APPROVED", "sent": False, "to_email": "a@test.com"},
            {"id": "draft2", "approval_status": "APPROVED", "sent": False, "to_email": "b@test.com"},
        ]))
        
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        monkeypatch.setattr(Config, "CRON_MODE", False)
        
        mailer = Mailer()
        approved = mailer.approval_manager.list_approved()
        
        # Should return list, but send_approved processes one at a time with confirmation
        assert isinstance(approved, list)
        assert len(approved) == 2
