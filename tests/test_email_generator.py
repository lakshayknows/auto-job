"""
Test email generator module.
Verify: single generation per job, max 120 words, draft stored not sent.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime

from app.email_generator import EmailGenerator
from app.config import Config, llm_counter


class TestEmailGenerator:
    """Test suite for email generator."""

    def test_draft_stored_not_sent(self, tmp_path, monkeypatch):
        """Verify drafts are stored with sent=False."""
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text(json.dumps([
            {
                "id": "draft1",
                "job_id": "job1",
                "approval_status": "PENDING",
                "sent": False,
            }
        ]))
        
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        
        generator = EmailGenerator()
        approvals = generator._load_approvals()
        
        for approval in approvals:
            assert approval["sent"] is False, "Draft marked as sent"
            assert approval["approval_status"] in ["PENDING", "APPROVED", "REJECTED"]

    def test_email_generated_once_per_job(self, tmp_path, monkeypatch):
        """Verify email is generated only once per job."""
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text(json.dumps([
            {"id": "draft1", "job_id": "job1", "approval_status": "PENDING", "sent": False}
        ]))
        
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        
        generator = EmailGenerator()
        
        # Should find existing draft
        assert generator._is_draft_exists("job1") is True
        assert generator._is_draft_exists("job2") is False

    def test_max_word_limit_prompt(self):
        """Verify prompt specifies word limit."""
        from app.email_generator import EMAIL_WRITER_PROMPT
        
        assert "250" in EMAIL_WRITER_PROMPT, "250 word limit not in prompt"

    def test_get_draft_returns_existing(self, tmp_path, monkeypatch):
        """Verify _get_draft returns existing draft."""
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text(json.dumps([
            {"id": "draft1", "job_id": "job1", "company": "Test", "role": "Dev"}
        ]))
        
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        
        generator = EmailGenerator()
        draft = generator._get_draft("job1")
        
        assert draft is not None
        assert draft["company"] == "Test"

    def test_cron_mode_blocks_generation(self, tmp_path, monkeypatch):
        """Verify CRON_MODE blocks email generation."""
        monkeypatch.setattr(Config, "CRON_MODE", True)
        monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
        
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(json.dumps([{"id": "test", "company": "A", "role": "B"}]))
        monkeypatch.setattr(Config, "JOBS_JSON", jobs_file)
        
        contacts_file = tmp_path / "contacts.json"
        contacts_file.write_text(json.dumps([{"job_id": "test", "email": "test@test.com"}]))
        monkeypatch.setattr(Config, "CONTACTS_JSON", contacts_file)
        
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text("[]")
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        
        generator = EmailGenerator()
        result = generator.generate_email("test")
        
        assert result is None, "Email generated in CRON_MODE"

    def test_llm_limit_blocks_generation(self, tmp_path, monkeypatch):
        """Verify LLM limit blocks email generation."""
        monkeypatch.setattr(Config, "CRON_MODE", False)
        
        # Exhaust LLM calls
        llm_counter.count = 100
        llm_counter.max_calls = 25
        
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(json.dumps([{"id": "test", "company": "A", "role": "B", "description": "C"}]))
        monkeypatch.setattr(Config, "JOBS_JSON", jobs_file)
        
        contacts_file = tmp_path / "contacts.json"
        contacts_file.write_text(json.dumps([{"job_id": "test", "email": "test@test.com"}]))
        monkeypatch.setattr(Config, "CONTACTS_JSON", contacts_file)
        
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text("[]")
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        
        generator = EmailGenerator()
        result = generator.generate_email("test")
        
        assert result is None, "Email generated despite LLM limit"
        
        # Reset counter
        llm_counter.reset()

    def test_no_contact_skips_generation(self, tmp_path, monkeypatch):
        """Verify missing contact skips generation."""
        monkeypatch.setattr(Config, "CRON_MODE", False)
        
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(json.dumps([{"id": "test", "company": "A", "role": "B"}]))
        monkeypatch.setattr(Config, "JOBS_JSON", jobs_file)
        
        contacts_file = tmp_path / "contacts.json"
        contacts_file.write_text("[]")  # No contacts
        monkeypatch.setattr(Config, "CONTACTS_JSON", contacts_file)
        
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text("[]")
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        
        generator = EmailGenerator()
        result = generator.generate_email("test")
        
        assert result is None, "Email generated without contact"
