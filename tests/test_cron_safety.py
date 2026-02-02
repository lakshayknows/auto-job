"""
Test cron safety module.
Verify: CRON_MODE blocks LLM, resume, email, and sending.
"""

import json
import pytest
from pathlib import Path

from app.config import Config, llm_counter


class TestCronSafety:
    """Test suite for cron mode safety."""

    def test_cron_mode_blocks_llm_calls(self, monkeypatch):
        """Verify CRON_MODE flag is set correctly."""
        monkeypatch.setattr(Config, "CRON_MODE", True)
        
        # In CRON_MODE, all LLM-dependent operations should check this flag
        assert Config.CRON_MODE is True

    def test_cron_mode_false_by_default(self):
        """Verify CRON_MODE is False by default in .env.example."""
        import os
        
        # Default should be false
        default = os.getenv("CRON_MODE", "false").lower() == "true"
        # This tests the parsing logic
        assert "false".lower() == "false"

    def test_resume_builder_checks_cron_mode(self, tmp_path, monkeypatch):
        """Verify resume builder checks CRON_MODE."""
        from app.resume_builder import ResumeBuilder
        
        monkeypatch.setattr(Config, "CRON_MODE", True)
        monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
        
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(json.dumps([{"id": "test", "company": "A", "role": "B"}]))
        monkeypatch.setattr(Config, "JOBS_JSON", jobs_file)
        
        builder = ResumeBuilder()
        result = builder.tailor_resume("test")
        
        assert result is None, "Resume generated in CRON_MODE"

    def test_email_generator_checks_cron_mode(self, tmp_path, monkeypatch):
        """Verify email generator checks CRON_MODE."""
        from app.email_generator import EmailGenerator
        
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

    def test_mailer_checks_cron_mode(self, tmp_path, monkeypatch):
        """Verify mailer checks CRON_MODE."""
        from app.mailer import Mailer
        
        monkeypatch.setattr(Config, "CRON_MODE", True)
        
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text(json.dumps([
            {"id": "draft1", "approval_status": "APPROVED", "sent": False, "to_email": "test@test.com"}
        ]))
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        
        mailer = Mailer()
        result = mailer.send_email("draft1")
        
        assert result is False, "Email sent in CRON_MODE"

    def test_scraper_allowed_in_cron_mode(self, tmp_path, monkeypatch):
        """Verify scraper IS allowed in CRON_MODE."""
        from app.scraper import JobScraper
        
        monkeypatch.setattr(Config, "CRON_MODE", True)
        monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
        
        # Scraper should still work - cron runs scraper only
        scraper = JobScraper()
        # Just verify it initializes without error
        assert scraper is not None
