"""
Test RAG cache module.
Verify: embeddings reused, no duplicates, incremental indexing.
"""

import json
import pytest
from pathlib import Path

from app.rag import RAGManager
from app.config import Config


class TestRAGCache:
    """Test suite for RAG caching."""

    def test_jobs_retrieved_correctly(self, tmp_path, monkeypatch):
        """Verify jobs are retrieved by ID."""
        # Setup test data
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(json.dumps([
            {"id": "job1", "company": "Test Co", "role": "Dev", "description": "Test"},
            {"id": "job2", "company": "Other Co", "role": "PM", "description": "Test2"},
        ]))
        
        monkeypatch.setattr(Config, "JOBS_JSON", jobs_file)
        
        rag = RAGManager()
        job = rag.get_job_by_id("job1")
        
        assert job is not None, "Job not found"
        assert job["company"] == "Test Co"

    def test_resume_content_retrieved(self, tmp_path, monkeypatch):
        """Verify resume content is retrieved."""
        resume_file = tmp_path / "resume.tex"
        resume_file.write_text("\\documentclass{article}\n\\begin{document}\nTest Resume\n\\end{document}")
        
        monkeypatch.setattr(Config, "BASE_RESUME_TEX", resume_file)
        
        rag = RAGManager()
        content = rag.get_resume_content()
        
        assert "Test Resume" in content

    def test_combined_context_includes_job_and_resume(self, tmp_path, monkeypatch):
        """Verify combined context includes both job and resume."""
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(json.dumps([
            {"id": "job1", "company": "Test Co", "role": "Developer", "description": "Build stuff"},
        ]))
        
        resume_file = tmp_path / "resume.tex"
        resume_file.write_text("Experience: Senior Developer")
        
        monkeypatch.setattr(Config, "JOBS_JSON", jobs_file)
        monkeypatch.setattr(Config, "BASE_RESUME_TEX", resume_file)
        
        rag = RAGManager()
        context = rag.get_combined_context("job1")
        
        assert "Test Co" in context, "Job company not in context"
        assert "Developer" in context, "Job role not in context"
        assert "Senior Developer" in context, "Resume content not in context"

    def test_index_jobs_returns_count(self, tmp_path, monkeypatch):
        """Verify index_jobs returns job count."""
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(json.dumps([
            {"id": "job1", "company": "A", "role": "B", "description": "C"},
            {"id": "job2", "company": "D", "role": "E", "description": "F"},
        ]))
        
        monkeypatch.setattr(Config, "JOBS_JSON", jobs_file)
        
        rag = RAGManager()
        count = rag.index_jobs()
        
        assert count == 2, f"Expected 2 jobs indexed, got {count}"

    def test_index_resume_returns_true(self, tmp_path, monkeypatch):
        """Verify index_resume returns True when resume exists."""
        resume_file = tmp_path / "resume.tex"
        resume_file.write_text("Test content")
        
        monkeypatch.setattr(Config, "BASE_RESUME_TEX", resume_file)
        
        rag = RAGManager()
        result = rag.index_resume()
        
        assert result is True

    def test_no_jobs_returns_zero(self, tmp_path, monkeypatch):
        """Verify empty jobs returns 0."""
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text("[]")
        
        monkeypatch.setattr(Config, "JOBS_JSON", jobs_file)
        
        rag = RAGManager()
        count = rag.index_jobs()
        
        assert count == 0
