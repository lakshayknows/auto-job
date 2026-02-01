"""
RAG module for retrieval-augmented generation.
Uses simple file-based retrieval to avoid embedding API quota issues.
"""

import json
from pathlib import Path
from typing import Optional

from app.config import Config


class RAGManager:
    """
    Manages RAG (Retrieval-Augmented Generation) for job automation.
    
    Uses simple file-based retrieval instead of vector embeddings
    to avoid API quota issues during testing.
    """

    def __init__(self):
        Config.ensure_directories()
        self.jobs_indexed = False
        self.resume_indexed = False

    def index_jobs(self) -> int:
        """
        Mark jobs as indexed (no actual embedding needed).
        Returns number of jobs available.
        """
        if not Config.JOBS_JSON.exists():
            print("No jobs.json found. Run scraper first.")
            return 0

        with open(Config.JOBS_JSON, "r", encoding="utf-8") as f:
            jobs = json.load(f)

        if not jobs:
            print("No jobs to index.")
            return 0

        self.jobs_indexed = True
        print(f"Jobs available for retrieval: {len(jobs)}")
        return len(jobs)

    def index_resume(self) -> bool:
        """
        Mark resume as indexed (no actual embedding needed).
        """
        if not Config.BASE_RESUME_TEX.exists():
            print("No base_resume.tex found.")
            return False

        self.resume_indexed = True
        print("Resume available for retrieval.")
        return True

    def build_index(self) -> dict:
        """
        Build index (mark files as available for retrieval).
        """
        print("Building RAG index...")

        result = {
            "jobs_indexed": self.index_jobs(),
            "resume_indexed": self.index_resume(),
        }

        print("RAG index build complete.")
        return result

    def get_job_by_id(self, job_id: str) -> Optional[dict]:
        """Get a job by its ID."""
        if not Config.JOBS_JSON.exists():
            return None

        with open(Config.JOBS_JSON, "r", encoding="utf-8") as f:
            jobs = json.load(f)

        for job in jobs:
            if job.get("id") == job_id:
                return job
        return None

    def get_resume_content(self) -> str:
        """Get the base resume content."""
        if not Config.BASE_RESUME_TEX.exists():
            return ""

        with open(Config.BASE_RESUME_TEX, "r", encoding="utf-8") as f:
            return f.read()

    def get_combined_context(self, job_id: str) -> str:
        """
        Get combined context for resume tailoring and email generation.
        Returns job description + base resume content.
        """
        context_parts = []

        # Get job
        job = self.get_job_by_id(job_id)
        if job:
            context_parts.append("=== TARGET JOB ===")
            context_parts.append(f"Company: {job.get('company', '')}")
            context_parts.append(f"Role: {job.get('role', '')}")
            context_parts.append(f"Description: {job.get('description', '')}")

        # Get resume
        resume = self.get_resume_content()
        if resume:
            context_parts.append("\n=== BASE RESUME ===")
            context_parts.append(resume)

        return "\n".join(context_parts)


def main():
    """Entry point for RAG module."""
    rag = RAGManager()
    rag.build_index()


if __name__ == "__main__":
    main()
