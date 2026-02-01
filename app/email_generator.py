"""
Email generator module for cold email drafting.
Uses RAG to create personalized, job-specific email drafts.
"""

import csv
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import Config, llm_counter
from app.rag import RAGManager


# RALPH Email Writer Prompt
EMAIL_WRITER_PROMPT = """# ROLE
You are a professional technical cold-email writer.

# AUDIENCE
Engineering managers / hiring teams.

# PURPOSE
Draft a concise, respectful cold email aligned to the job role.

# LIMITS
- DO NOT sound automated
- DO NOT exaggerate experience
- Maximum 120 words
- Be concise
- Avoid unnecessary verbosity
- Prefer structured output over prose

# INPUT
## Target Job:
Company: {company}
Role: {role}
Description: {job_description}

## Candidate Resume Summary:
{resume_summary}

# OUTPUT
Write ONLY the email body. Do not include subject line, greeting, or signature.
The email should:
1. Open with a compelling hook related to the role
2. Briefly highlight 1-2 relevant experiences that match the job
3. Express genuine interest in the company's mission/product
4. End with a soft call-to-action (e.g., "I'd love to discuss...")

Do not include any explanations or formatting outside the email body.
"""


class EmailGenerator:
    """
    Email draft generator using LangChain and Google Gemini.
    
    Features:
    - RAG-powered personalization
    - Lazy generation (only generates once per job)
    - Max 120 words per email
    - Drafts only - never sends
    """

    def __init__(self):
        Config.ensure_directories()
        self.rag = RAGManager()
        self.llm = ChatGoogleGenerativeAI(
            model=Config.LLM_MODEL,
            google_api_key=Config.GOOGLE_API_KEY,
            temperature=0.7,
        )

    def _get_job_by_id(self, job_id: str) -> Optional[dict]:
        """Get job details by ID."""
        if not Config.JOBS_JSON.exists():
            return None

        with open(Config.JOBS_JSON, "r", encoding="utf-8") as f:
            jobs = json.load(f)

        for job in jobs:
            if job.get("id") == job_id:
                return job
        return None

    def _get_contact_by_job_id(self, job_id: str) -> Optional[dict]:
        """Get contact details by job ID."""
        if not Config.CONTACTS_JSON.exists():
            return None

        with open(Config.CONTACTS_JSON, "r", encoding="utf-8") as f:
            contacts = json.load(f)

        for contact in contacts:
            if contact.get("job_id") == job_id:
                return contact
        return None

    def _load_approvals(self) -> list[dict]:
        """Load existing approvals."""
        if not Config.APPROVALS_JSON.exists():
            return []

        with open(Config.APPROVALS_JSON, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

    def _save_approvals(self, approvals: list[dict]) -> None:
        """Save approvals to JSON and CSV."""
        # Save JSON
        with open(Config.APPROVALS_JSON, "w", encoding="utf-8") as f:
            json.dump(approvals, f, indent=2, ensure_ascii=False)

        # Save CSV
        if approvals:
            fieldnames = sorted(set().union(*[a.keys() for a in approvals]))
            with open(Config.APPROVALS_CSV, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(approvals)

    def _is_draft_exists(self, job_id: str) -> bool:
        """Check if a draft already exists for this job."""
        approvals = self._load_approvals()
        return any(a.get("job_id") == job_id for a in approvals)

    def _get_draft(self, job_id: str) -> Optional[dict]:
        """Get existing draft by job ID."""
        approvals = self._load_approvals()
        for a in approvals:
            if a.get("job_id") == job_id:
                return a
        return None

    def _slugify(self, text: str) -> str:
        """Convert text to a safe filename slug."""
        text = text.lower()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[-\s]+", "_", text)
        return text[:50]

    def _get_resume_path(self, job: dict) -> Optional[Path]:
        """Get the compiled resume path for a job."""
        company_slug = self._slugify(job.get("company", "unknown"))
        role_slug = self._slugify(job.get("role", "unknown"))
        filename_base = f"{job['id']}_{company_slug}_{role_slug}"

        pdf_path = Config.COMPILED_RESUME_DIR / f"{filename_base}.pdf"
        return pdf_path if pdf_path.exists() else None

    def _extract_resume_summary(self) -> str:
        """Extract a summary from the base resume for the prompt."""
        if not Config.BASE_RESUME_TEX.exists():
            return "Software engineer with experience in AI/ML and backend development."

        with open(Config.BASE_RESUME_TEX, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract key sections (simplified)
        summary_match = re.search(
            r"\\section\{Summary\}(.*?)(?=\\section|\\end\{document\})",
            content,
            re.DOTALL,
        )
        if summary_match:
            summary = summary_match.group(1)
            # Clean LaTeX commands
            summary = re.sub(r"\\[a-zA-Z]+(\{[^}]*\})?", "", summary)
            summary = re.sub(r"[{}]", "", summary)
            summary = summary.strip()[:500]
            return summary

        return "Software engineer with experience in AI/ML and backend development."

    def generate_email(self, job_id: str, force: bool = False) -> Optional[dict]:
        """
        Generate an email draft for a specific job.
        
        Args:
            job_id: ID of the job to generate email for
            force: If True, regenerate even if draft exists
            
        Returns:
            Draft dictionary, or None if failed
        """
        # Check if draft exists (lazy loading)
        if not force and self._is_draft_exists(job_id):
            print(f"Draft already exists for job {job_id}")
            return self._get_draft(job_id)

        job = self._get_job_by_id(job_id)
        if not job:
            print(f"Job {job_id} not found.")
            return None

        contact = self._get_contact_by_job_id(job_id)
        if not contact:
            print(f"No contact found for job {job_id}. Skipping.")
            return None

        # Check CRON_MODE
        if Config.CRON_MODE:
            print("CRON_MODE is enabled. Skipping email generation.")
            return None

        # Check LLM call limit
        if not llm_counter.can_call():
            print("LLM call limit reached. Skipping email generation.")
            return None

        print(f"Generating email for {job['company']} - {job['role']}...")

        # Get resume summary
        resume_summary = self._extract_resume_summary()

        # Generate email
        prompt = EMAIL_WRITER_PROMPT.format(
            company=job.get("company", ""),
            role=job.get("role", ""),
            job_description=job.get("description", "")[:2000],
            resume_summary=resume_summary,
        )

        try:
            llm_counter.increment()
            response = self.llm.invoke(prompt)
            email_body = response.content.strip()

            # Create subject line
            subject = f"Application for {job.get('role', 'Position')} at {job.get('company', 'Your Company')}"

            # Get resume path
            resume_path = self._get_resume_path(job)

            # Create draft
            draft = {
                "id": str(uuid.uuid4()),
                "job_id": job_id,
                "company": job.get("company", ""),
                "role": job.get("role", ""),
                "to_email": contact.get("email", ""),
                "subject": subject,
                "body": email_body,
                "resume_path": str(resume_path) if resume_path else None,
                "approval_status": "PENDING",
                "approved_at": None,
                "sent": False,
                "sent_at": None,
                "regenerated": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            # Save to cache
            cache_path = Config.EMAILS_CACHE / f"{job_id}.json"
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(draft, f, indent=2)

            # Add to approvals
            approvals = self._load_approvals()

            # Remove old draft if force regenerating
            if force:
                approvals = [a for a in approvals if a.get("job_id") != job_id]
                draft["regenerated"] = True

            approvals.append(draft)
            self._save_approvals(approvals)

            print(f"Generated email draft for {job['company']}")
            return draft

        except Exception as e:
            print(f"Error generating email: {e}")
            return None

    def generate_all_emails(self, force: bool = False) -> dict:
        """
        Generate email drafts for all jobs with contacts and resumes.
        
        Returns:
            Summary of processing results
        """
        if not Config.CONTACTS_JSON.exists():
            print("No contacts.json found. Run scraper first.")
            return {"total": 0, "success": 0, "cached": 0, "failed": 0}

        with open(Config.CONTACTS_JSON, "r", encoding="utf-8") as f:
            contacts = json.load(f)

        job_ids = [c["job_id"] for c in contacts]

        results = {"total": len(job_ids), "success": 0, "cached": 0, "failed": 0}

        for job_id in job_ids:
            if not llm_counter.can_call():
                print("LLM call limit reached. Stopping email generation.")
                break

            if self._is_draft_exists(job_id) and not force:
                results["cached"] += 1
                continue

            draft = self.generate_email(job_id, force=force)
            if draft:
                results["success"] += 1
            else:
                results["failed"] += 1

        print(f"Email generation complete: {results}")
        return results


def main():
    """Entry point for email generator module."""
    generator = EmailGenerator()
    generator.generate_all_emails()


if __name__ == "__main__":
    main()
