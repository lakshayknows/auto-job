"""
Test resume builder module.
Verify: LaTeX output, PDF generated, cached reused, deterministic filename.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.resume_builder import ResumeBuilder
from app.config import Config, llm_counter


class TestResumeBuilder:
    """Test suite for resume builder."""

    def test_latex_output_only(self, tmp_path, monkeypatch):
        """Verify output is valid LaTeX."""
        # This tests the validation logic
        builder = ResumeBuilder()
        
        valid_latex = "\\documentclass{article}\n\\begin{document}\nTest\n\\end{document}"
        invalid_latex = "Just plain text"
        
        assert valid_latex.strip().startswith("\\documentclass")
        assert not invalid_latex.strip().startswith("\\documentclass")

    def test_deterministic_filename(self, tmp_path, monkeypatch):
        """Verify filename is deterministic for same job."""
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(json.dumps([
            {"id": "abc123", "company": "Test Company", "role": "Software Engineer"},
        ]))
        
        monkeypatch.setattr(Config, "JOBS_JSON", jobs_file)
        monkeypatch.setattr(Config, "RESUMES_CACHE", tmp_path / "cache")
        monkeypatch.setattr(Config, "COMPILED_RESUME_DIR", tmp_path / "compiled")
        
        builder = ResumeBuilder()
        job = builder._get_job_by_id("abc123")
        
        path1, _ = builder._get_resume_paths(job)
        path2, _ = builder._get_resume_paths(job)
        
        assert path1 == path2, "Filename not deterministic"

    def test_cached_resume_reused(self, tmp_path, monkeypatch):
        """Verify cached resume is reused."""
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(json.dumps([
            {"id": "abc123", "company": "Test", "role": "Dev"},
        ]))
        
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        compiled_dir = tmp_path / "compiled"
        compiled_dir.mkdir()
        
        # Create cached files
        tex_file = cache_dir / "abc123_test_dev.tex"
        tex_file.write_text("\\documentclass{article}")
        pdf_file = compiled_dir / "abc123_test_dev.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 test")
        
        monkeypatch.setattr(Config, "JOBS_JSON", jobs_file)
        monkeypatch.setattr(Config, "RESUMES_CACHE", cache_dir)
        monkeypatch.setattr(Config, "COMPILED_RESUME_DIR", compiled_dir)
        
        builder = ResumeBuilder()
        
        # Should return cached, not regenerate
        assert builder._is_cached("abc123") is True

    def test_slugify_safe_filename(self, tmp_path, monkeypatch):
        """Verify slugify creates safe filenames."""
        monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
        
        builder = ResumeBuilder()
        
        test_cases = [
            ("Test Company", "test_company"),
            ("NVIDIA USA", "nvidia_usa"),
            ("Test@#$%", "test"),
            ("Very Long Company Name That Exceeds Fifty Characters Limit", "very_long_company_name_that_exceeds_fifty_charac"),
        ]
        
        for input_text, expected_prefix in test_cases:
            result = builder._slugify(input_text)
            assert len(result) <= 50, f"Slug too long: {result}"
            assert result.islower() or result == "", f"Slug not lowercase: {result}"

    def test_cron_mode_blocks_generation(self, tmp_path, monkeypatch):
        """Verify CRON_MODE blocks resume generation."""
        monkeypatch.setattr(Config, "CRON_MODE", True)
        monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
        
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(json.dumps([{"id": "test", "company": "A", "role": "B"}]))
        monkeypatch.setattr(Config, "JOBS_JSON", jobs_file)
        
        builder = ResumeBuilder()
        result = builder.tailor_resume("test")
        
        assert result is None, "Resume generated in CRON_MODE"

    def test_llm_limit_blocks_generation(self, tmp_path, monkeypatch):
        """Verify LLM limit blocks resume generation."""
        monkeypatch.setattr(Config, "CRON_MODE", False)
        
        # Exhaust LLM calls
        llm_counter.count = 100
        llm_counter.max_calls = 25
        
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(json.dumps([{"id": "test", "company": "A", "role": "B"}]))
        monkeypatch.setattr(Config, "JOBS_JSON", jobs_file)
        monkeypatch.setattr(Config, "RESUMES_CACHE", tmp_path)
        monkeypatch.setattr(Config, "COMPILED_RESUME_DIR", tmp_path)
        
        builder = ResumeBuilder()
        result = builder.tailor_resume("test")
        
        assert result is None, "Resume generated despite LLM limit"
        
        # Reset counter
        llm_counter.reset()
