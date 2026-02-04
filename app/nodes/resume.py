"""Resume tailoring node.

Tailors LaTeX resume for specific job roles using RAG context.
Implements logic as defined in resume_tailor.md.
"""

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import (
    PROMPTS_DIR,
    RESUME_DIR,
    get_config,
    get_logger,
)
from app.state import JobState

logger = get_logger("resume")


def load_prompt(name: str) -> str:
    """Load prompt from markdown file.

    Args:
        name: Prompt file name without extension

    Returns:
        Prompt content
    """
    prompt_path = PROMPTS_DIR / f"{name}.md"
    if prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def load_base_resume() -> str:
    """Load base resume LaTeX content.

    Returns:
        Resume LaTeX content
    """
    resume_path = RESUME_DIR / "base_resume.tex"
    with open(resume_path, "r", encoding="utf-8") as f:
        return f.read()


def get_cache_path(job_id: str) -> Path:
    """Get cache path for tailored resume.

    Args:
        job_id: Job identifier

    Returns:
        Path to cached resume
    """
    return RESUME_DIR / "compiled" / f"resume_{job_id[:8]}.tex"


def get_pdf_path(job_id: str) -> Path:
    """Get path for compiled PDF.

    Args:
        job_id: Job identifier

    Returns:
        Path to PDF file
    """
    return RESUME_DIR / "compiled" / f"resume_{job_id[:8]}.pdf"


def compile_latex_to_pdf(tex_path: Path) -> Optional[Path]:
    """Compile LaTeX file to PDF.

    Args:
        tex_path: Path to .tex file

    Returns:
        Path to generated PDF or None on failure
    """
    try:
        output_dir = tex_path.parent
        result = subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                "-output-directory",
                str(output_dir),
                str(tex_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(RESUME_DIR),  # Run from resume dir for includes
        )

        pdf_path = tex_path.with_suffix(".pdf")
        if pdf_path.exists():
            logger.info(f"Compiled PDF: {pdf_path}")
            return pdf_path
        else:
            logger.error(f"PDF compilation failed: {result.stderr}")
            return None

    except subprocess.TimeoutExpired:
        logger.error("LaTeX compilation timed out")
        return None
    except FileNotFoundError:
        logger.error("pdflatex not found - ensure texlive is installed")
        return None
    except Exception as e:
        logger.error(f"Compilation error: {e}")
        return None


def tailor_resume(state: JobState) -> JobState:
    """LangGraph node: Tailor resume for specific job.

    Args:
        state: Current job state with job_data and rag_context

    Returns:
        Updated state with resume paths
    """
    config = get_config()

    # Check CRON_MODE
    if config.cron_mode:
        logger.info("CRON_MODE active - skipping resume tailoring")
        return {
            **state,
            "should_skip": True,
            "skip_reason": "CRON_MODE active",
        }

    job_id = state.get("job_id", "unknown")
    job_data = state.get("job_data", {})
    rag_context = state.get("rag_context", {})

    # Check cache
    cache_path = get_cache_path(job_id)
    pdf_path = get_pdf_path(job_id)

    if cache_path.exists() and pdf_path.exists():
        logger.info(f"Using cached resume: {cache_path}")
        return {
            **state,
            "resume_tex_path": str(cache_path),
            "resume_pdf_path": str(pdf_path),
        }

    try:
        # Load base resume
        base_resume = load_base_resume()

        # Load system prompt
        system_prompt = load_prompt("resume_tailor")

        # Build context for tailoring
        job_context = f"""
Company: {job_data.get('company', 'Unknown')}
Role: {job_data.get('role', 'Software Engineer')}
Description: {job_data.get('description', '')[:1500]}

Required Skills: {', '.join(rag_context.get('job_skills', [])[:10])}
Tech Stack: {', '.join(rag_context.get('job_tech_stack', [])[:10])}
"""

        resume_context = f"""
Matching Experience:
{chr(10).join(rag_context.get('resume_experience', [])[:3])}

Matching Projects:
{chr(10).join(rag_context.get('resume_projects', [])[:3])}

Matching Skills: {', '.join(rag_context.get('resume_skills', [])[:10])}
"""

        # Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt if system_prompt else """You are a resume tailoring agent.
Tailor the LaTeX resume for the specific job role.

CONSTRAINTS:
- Output LaTeX ONLY
- Do NOT change document structure
- Do NOT add fake experience
- Do NOT exceed one page
- Reuse existing projects where possible

GUIDELINES:
- Reorder bullets to match job relevance
- Adjust wording, not facts
- Maintain technical, professional tone

OUTPUT: Return ONLY valid LaTeX code. No explanations."""),
            ("human", """## Job Context
{job_context}

## Resume Context
{resume_context}

## Base Resume LaTeX
{base_resume}

Tailor this resume for the job. Return ONLY valid LaTeX."""),
        ])

        # Initialize LLM
        llm = ChatGoogleGenerativeAI(
            model=config.llm.model_name,
            google_api_key=config.llm.google_api_key,
            temperature=config.llm.temperature,
        )

        # Generate tailored resume
        chain = prompt | llm
        response = chain.invoke({
            "job_context": job_context,
            "resume_context": resume_context,
            "base_resume": base_resume,
        })

        # Extract LaTeX from response
        tailored_latex = response.content

        # Clean up response (remove markdown code blocks if present)
        if "```latex" in tailored_latex:
            tailored_latex = tailored_latex.split("```latex")[1].split("```")[0]
        elif "```" in tailored_latex:
            tailored_latex = tailored_latex.split("```")[1].split("```")[0]

        tailored_latex = tailored_latex.strip()

        # Validate LaTeX (basic check)
        if not tailored_latex.startswith("\\documentclass"):
            logger.warning("Invalid LaTeX output - using base resume")
            tailored_latex = base_resume

        # Save tailored resume
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(tailored_latex)

        logger.info(f"Saved tailored resume: {cache_path}")

        # Compile to PDF
        compiled_pdf = compile_latex_to_pdf(cache_path)

        # Update token count
        llm_calls = state.get("llm_calls", 0) + 1
        total_tokens = state.get("total_tokens", 0) + len(tailored_latex) // 4

        return {
            **state,
            "resume_tex_path": str(cache_path),
            "resume_pdf_path": str(compiled_pdf) if compiled_pdf else None,
            "llm_calls": llm_calls,
            "total_tokens": total_tokens,
        }

    except Exception as e:
        logger.exception("Resume tailoring failed")
        return {
            **state,
            "errors": state.get("errors", []) + [f"Resume error: {e}"],
        }
