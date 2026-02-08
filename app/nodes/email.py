"""Email drafting node.

Drafts professional cold emails for job applications.
Implements logic as defined in email_writer.md.
"""

import json
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import DATA_DIR, PROMPTS_DIR, get_config, get_logger
from app.state import JobState

logger = get_logger("email")

# Hard limit per email_writer.md
MAX_WORDS = 200


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


def get_cache_path(job_id: str) -> Path:
    """Get cache path for email draft.

    Args:
        job_id: Job identifier

    Returns:
        Path to cached email
    """
    return DATA_DIR / f"email_draft_{job_id[:8]}.json"


def count_words(text: str) -> int:
    """Count words in text.

    Args:
        text: Text to count

    Returns:
        Word count
    """
    return len(text.split())


def truncate_to_word_limit(text: str, max_words: int = MAX_WORDS) -> str:
    """Truncate text to word limit.

    Args:
        text: Text to truncate
        max_words: Maximum words allowed

    Returns:
        Truncated text
    """
    words = text.split()
    if len(words) <= max_words:
        return text

    logger.warning(f"Email exceeded {max_words} words ({len(words)}), truncating")
    return " ".join(words[:max_words])


def draft_email(state: JobState) -> JobState:
    """LangGraph node: Draft cold email for job application.

    Args:
        state: Current job state

    Returns:
        Updated state with email_draft

    Raises:
        CronModeError: If CRON_MODE is active (hard block)
    """
    from app.nodes.guards import assert_not_cron_mode

    # CRON_MODE: Hard circuit breaker - email drafting is blocked
    assert_not_cron_mode("email drafting")

    config = get_config()
    job_id = state.get("job_id", "unknown")
    job_data = state.get("job_data", {})
    rag_context = state.get("rag_context", {})

    # Check cache
    cache_path = get_cache_path(job_id)
    if cache_path.exists():
        logger.info(f"Using cached email draft: {cache_path}")
        with open(cache_path, "r") as f:
            cached = json.load(f)
        return {
            **state,
            "email_draft": cached.get("body"),
            "email_subject": cached.get("subject"),
        }

    try:
        # Load system prompt
        system_prompt = load_prompt("email_writer")

        # Build context
        company = job_data.get("company", "the company")
        role = job_data.get("role", "Software Engineer")
        description = job_data.get("description", "")[:500]

        resume_summary = "\n".join(
            [f"- {exp[:100]}" for exp in rag_context.get("resume_experience", [])[:2]]
        )

        matching_skills = ", ".join(
            set(rag_context.get("job_skills", []))
            & set(rag_context.get("resume_skills", []))
        )[:200]

        # Create prompt
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        system_prompt
                        if system_prompt
                        else """You are a professional technical cold-email writer.

HARD LIMIT: Maximum 200 words

RULES:
- Do NOT sound automated
- Do NOT exaggerate experience
- Do NOT include emojis
- Do NOT include subject line or signature
- Do NOT repeat resume verbatim

STRUCTURE:
- Opening line specific to the role
- 1-2 concrete qualifications
- Genuine interest in company/product
- Soft call-to-action

OUTPUT: Return ONLY the email body text. No explanations."""
                    ),
                ),
                (
                    "human",
                    """## Job Details
Company: {company}
Role: {role}
Description: {description}

## Resume Summary
{resume_summary}

## Matching Skills
{matching_skills}

Write a concise job application email (max 200 words). Return ONLY the email body.""",
                ),
            ]
        )

        # Initialize LLM (uses centralized Gemini 2.5 config)
        llm = ChatGoogleGenerativeAI(
            model=config.llm.model_name,
            google_api_key=config.llm.google_api_key,
            temperature=config.llm.temperature,
        )

        # Generate email
        chain = prompt | llm
        response = chain.invoke(
            {
                "company": company,
                "role": role,
                "description": description,
                "resume_summary": resume_summary
                or "Relevant experience in software development",
                "matching_skills": matching_skills or "Python, AI/ML",
            }
        )

        email_body = response.content.strip()

        # Enforce word limit
        email_body = truncate_to_word_limit(email_body, MAX_WORDS)

        # Generate subject line
        subject = f"Application for {role} at {company}"

        # Cache the draft
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(
                {
                    "job_id": job_id,
                    "subject": subject,
                    "body": email_body,
                    "word_count": count_words(email_body),
                },
                f,
                indent=2,
            )

        logger.info(f"Drafted email for {job_id}: {count_words(email_body)} words")

        # Update token count
        llm_calls = state.get("llm_calls", 0) + 1
        total_tokens = state.get("total_tokens", 0) + len(email_body) // 4

        return {
            **state,
            "email_draft": email_body,
            "email_subject": subject,
            "llm_calls": llm_calls,
            "total_tokens": total_tokens,
        }

    except Exception as e:
        logger.exception("Email drafting failed")
        return {
            **state,
            "errors": state.get("errors", []) + [f"Email error: {e}"],
        }
