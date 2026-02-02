"""
Test scraper module.
Verify: ≤100 jobs, required fields, no LinkedIn, no empty descriptions.
"""

import json
import pytest
from pathlib import Path

from app.scraper import JobScraper
from app.config import Config


class TestScraper:
    """Test suite for job scraper."""

    def test_max_100_jobs(self, tmp_path, monkeypatch):
        """Verify ≤100 jobs are scraped."""
        monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
        monkeypatch.setattr(Config, "JOBS_JSON", tmp_path / "jobs.json")
        
        scraper = JobScraper()
        jobs = scraper.scrape_remoteok()
        
        assert len(jobs) <= 100, f"Scraped {len(jobs)} jobs, expected ≤100"

    def test_required_fields_exist(self, tmp_path, monkeypatch):
        """Verify all required fields exist in scraped jobs."""
        monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
        monkeypatch.setattr(Config, "JOBS_JSON", tmp_path / "jobs.json")
        
        scraper = JobScraper()
        jobs = scraper.scrape_remoteok()
        
        required_fields = ["id", "company", "role", "description", "url", "scraped_at", "source"]
        
        for job in jobs[:5]:  # Check first 5 jobs
            for field in required_fields:
                assert field in job, f"Missing required field: {field}"
                assert job[field] is not None, f"Field {field} is None"

    def test_no_linkedin_urls(self, tmp_path, monkeypatch):
        """Verify no LinkedIn URLs in scraped jobs."""
        monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
        monkeypatch.setattr(Config, "JOBS_JSON", tmp_path / "jobs.json")
        
        scraper = JobScraper()
        jobs = scraper.scrape_remoteok()
        
        for job in jobs:
            url = job.get("url", "").lower()
            assert "linkedin.com" not in url, f"LinkedIn URL found: {url}"

    def test_no_empty_descriptions(self, tmp_path, monkeypatch):
        """Verify no empty job descriptions."""
        monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
        monkeypatch.setattr(Config, "JOBS_JSON", tmp_path / "jobs.json")
        
        scraper = JobScraper()
        jobs = scraper.scrape_remoteok()
        
        for job in jobs[:10]:  # Check first 10 jobs
            desc = job.get("description", "")
            assert len(desc) > 0, f"Empty description for job {job.get('id')}"

    def test_save_results_creates_files(self, tmp_path, monkeypatch):
        """Verify save_results creates JSON and CSV files."""
        monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
        monkeypatch.setattr(Config, "JOBS_JSON", tmp_path / "jobs.json")
        monkeypatch.setattr(Config, "JOBS_CSV", tmp_path / "jobs.csv")
        monkeypatch.setattr(Config, "CONTACTS_JSON", tmp_path / "contacts.json")
        monkeypatch.setattr(Config, "CONTACTS_CSV", tmp_path / "contacts.csv")
        
        scraper = JobScraper()
        scraper.jobs = [{"id": "test", "company": "Test", "role": "Dev", "description": "Test job"}]
        scraper.save_results()
        
        assert (tmp_path / "jobs.json").exists(), "jobs.json not created"
        assert (tmp_path / "jobs.csv").exists(), "jobs.csv not created"
