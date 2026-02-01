"""
Resume builder module for LaTeX resume tailoring.
Uses RAG to tailor resumes to specific job descriptions.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import Config, llm_counter
from app.rag import RAGManager


# RALPH Resume Tailor Prompt
RESUME_TAILOR_PROMPT = """# ROLE
You are an expert technical recruiter and resume optimizer.

# AUDIENCE
Hiring managers for the provided job description.

# PURPOSE
Tailor the candidate's resume to match the job description
WITHOUT lying or inventing experience.

# LIMITS
- Preserve factual accuracy
- Do not add skills not present in the base resume
- Optimize wording, ordering, and emphasis only
- Be concise
- Avoid unnecessary verbosity
- Prefer structured output over prose

# INPUT
## Target Job Description:
{job_description}

## Base Resume (LaTeX):
{base_resume}

# OUTPUT
Output ONLY valid LaTeX code that can be compiled with pdflatex.
Do not include any explanations, comments outside LaTeX, or markdown formatting.
Start directly with \\documentclass and end with \\end{{document}}.
Ensure the LaTeX compiles cleanly without errors.
"""


class ResumeBuilder:
    """
    Resume tailoring system using LangChain and Google Gemini.
    
    Features:
    - LaTeX-only output
    - Lazy generation (only generates if not cached)
    - Compiles via pdflatex
    - Deterministic filenames for caching
    """

    def __init__(self):
        Config.ensure_directories()
        self.rag = RAGManager()
        self.llm = ChatGoogleGenerativeAI(
            model=Config.LLM_MODEL,
            google_api_key=Config.GOOGLE_API_KEY,
            temperature=0.3,
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

    def _slugify(self, text: str) -> str:
        """Convert text to a safe filename slug."""
        text = text.lower()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[-\s]+", "_", text)
        return text[:50]

    def _get_resume_paths(self, job: dict) -> tuple[Path, Path]:
        """Get cached and compiled resume paths for a job."""
        company_slug = self._slugify(job.get("company", "unknown"))
        role_slug = self._slugify(job.get("role", "unknown"))
        filename_base = f"{job['id']}_{company_slug}_{role_slug}"

        cached_tex = Config.RESUMES_CACHE / f"{filename_base}.tex"
        compiled_pdf = Config.COMPILED_RESUME_DIR / f"{filename_base}.pdf"

        return cached_tex, compiled_pdf

    def _is_cached(self, job_id: str) -> bool:
        """Check if resume is already cached for this job."""
        job = self._get_job_by_id(job_id)
        if not job:
            return False

        cached_tex, compiled_pdf = self._get_resume_paths(job)
        return cached_tex.exists() and compiled_pdf.exists()

    def _load_base_resume(self) -> str:
        """Load the base resume LaTeX content."""
        if not Config.BASE_RESUME_TEX.exists():
            raise FileNotFoundError(
                f"Base resume not found at {Config.BASE_RESUME_TEX}"
            )

        with open(Config.BASE_RESUME_TEX, "r", encoding="utf-8") as f:
            return f.read()

    def tailor_resume(self, job_id: str, force: bool = False) -> Optional[Path]:
        """
        Generate a tailored resume for a specific job.
        
        Args:
            job_id: ID of the job to tailor resume for
            force: If True, regenerate even if cached
            
        Returns:
            Path to compiled PDF, or None if failed
        """
        job = self._get_job_by_id(job_id)
        if not job:
            print(f"Job {job_id} not found.")
            return None

        cached_tex, compiled_pdf = self._get_resume_paths(job)

        # Check cache (lazy loading)
        if not force and cached_tex.exists() and compiled_pdf.exists():
            print(f"Resume already cached for {job['company']} - {job['role']}")
            return compiled_pdf

        # Check CRON_MODE
        if Config.CRON_MODE:
            print("CRON_MODE is enabled. Skipping resume generation.")
            return None

        # Check LLM call limit
        if not llm_counter.can_call():
            print("LLM call limit reached. Skipping resume generation.")
            return None

        print(f"Tailoring resume for {job['company']} - {job['role']}...")

        # Load base resume
        try:
            base_resume = self._load_base_resume()
        except FileNotFoundError as e:
            print(str(e))
            return None

        # Get job description
        job_description = f"""
Company: {job.get('company', '')}
Role: {job.get('role', '')}
Description: {job.get('description', '')}
"""

        # Generate tailored resume
        prompt = RESUME_TAILOR_PROMPT.format(
            job_description=job_description,
            base_resume=base_resume,
        )

        try:
            llm_counter.increment()
            response = self.llm.invoke(prompt)
            latex_content = response.content

            # Clean up response (remove markdown code blocks if present)
            latex_content = re.sub(r"^```latex\s*", "", latex_content)
            latex_content = re.sub(r"^```\s*", "", latex_content)
            latex_content = re.sub(r"\s*```$", "", latex_content)

            # Validate LaTeX structure
            if not latex_content.strip().startswith("\\documentclass"):
                print("Invalid LaTeX output. Missing \\documentclass.")
                return None

            # Save to cache
            with open(cached_tex, "w", encoding="utf-8") as f:
                f.write(latex_content)

            print(f"Saved tailored LaTeX to {cached_tex}")

            # Compile to PDF
            pdf_path = self.compile_resume(cached_tex)
            return pdf_path

        except Exception as e:
            print(f"Error tailoring resume: {e}")
            return None

    def compile_resume(self, tex_path: Path) -> Optional[Path]:
        """
        Compile LaTeX file to PDF using pdflatex.
        
        Args:
            tex_path: Path to .tex file
            
        Returns:
            Path to compiled PDF, or None if failed
        """
        if not tex_path.exists():
            print(f"LaTeX file not found: {tex_path}")
            return None

        print(f"Compiling {tex_path}...")

        # Ensure output directory exists
        Config.COMPILED_RESUME_DIR.mkdir(parents=True, exist_ok=True)

        try:
            # Run pdflatex twice for proper cross-references
            for _ in range(2):
                result = subprocess.run(
                    [
                        "pdflatex",
                        "-interaction=nonstopmode",
                        f"-output-directory={Config.COMPILED_RESUME_DIR}",
                        str(tex_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

            # Check for PDF output
            pdf_name = tex_path.stem + ".pdf"
            pdf_path = Config.COMPILED_RESUME_DIR / pdf_name

            if pdf_path.exists():
                print(f"Compiled resume: {pdf_path}")

                # Clean up auxiliary files
                for ext in [".aux", ".log", ".out"]:
                    aux_file = Config.COMPILED_RESUME_DIR / (tex_path.stem + ext)
                    if aux_file.exists():
                        aux_file.unlink()

                return pdf_path
            else:
                print(f"PDF compilation failed. Check LaTeX output.")
                print(result.stdout[-2000:] if result.stdout else "No output")
                return None

        except subprocess.TimeoutExpired:
            print("LaTeX compilation timed out.")
            return None
        except FileNotFoundError:
            print("pdflatex not found. Please install LaTeX.")
            return None
        except Exception as e:
            print(f"Error compiling resume: {e}")
            return None

    def tailor_all_resumes(self, force: bool = False) -> dict:
        """
        Generate tailored resumes for all jobs with contacts.
        Only processes jobs that have discovered emails.
        
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
                print("LLM call limit reached. Stopping resume generation.")
                break

            if self._is_cached(job_id) and not force:
                results["cached"] += 1
                continue

            pdf_path = self.tailor_resume(job_id, force=force)
            if pdf_path:
                results["success"] += 1
            else:
                results["failed"] += 1

        print(f"Resume tailoring complete: {results}")
        return results


def main():
    """Entry point for resume builder module."""
    builder = ResumeBuilder()
    builder.tailor_all_resumes()


if __name__ == "__main__":
    main()
