"""Job discovery and email extraction node.

Discovers jobs from legal public sources and extracts company contact emails.
Focuses on fresher/intern AI engineering roles.
Follows strict legal and ethical guidelines as defined in scraper.md.
"""

import asyncio
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from app.config import DATA_DIR, get_config, get_logger, log_activity
from app.state import JobState
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

logger = get_logger("scraper")

# Allowed email patterns
ALLOWED_EMAIL_PREFIXES = [
    "careers",
    "jobs",
    "hiring",
    "hr",
    "talent",
    "recruiting",
    "apply",
    "team",
]

# Allowed paths for crawling
ALLOWED_PATHS = [
    "/careers",
    "/jobs",
    "/join-us",
    "/about",
    "/contact",
    "/work",
    "/team",
]

# Disallowed domains
BLOCKED_DOMAINS = ["linkedin.com", "facebook.com", "twitter.com", "x.com"]

# Target job keywords for fresher/intern AI roles
TARGET_KEYWORDS = [
    "ai",
    "ml",
    "machine learning",
    "deep learning",
    "llm",
    "nlp",
    "python",
    "backend",
    "data scientist",
    "data engineer",
    "intern",
    "fresher",
    "junior",
    "entry level",
    "entry-level",
    "graduate",
    "new grad",
    "associate",
    "trainee",
]


def is_valid_email_prefix(email: str) -> bool:
    """Check if email has an allowed prefix.

    Args:
        email: Email address to check

    Returns:
        True if email prefix is allowed
    """
    local_part = email.split("@")[0].lower()
    return any(prefix in local_part for prefix in ALLOWED_EMAIL_PREFIXES)


def extract_emails_from_text(text: str) -> list[str]:
    """Extract email addresses from text.

    Args:
        text: Text content to search

    Returns:
        List of valid email addresses found
    """
    pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    emails = re.findall(pattern, text)
    return [e.lower() for e in emails if "@" in e]


def is_allowed_domain(url: str) -> bool:
    """Check if URL domain is allowed for scraping.

    Args:
        url: URL to check

    Returns:
        True if domain is allowed
    """
    try:
        domain = urlparse(url).netloc.lower()
        return not any(blocked in domain for blocked in BLOCKED_DOMAINS)
    except Exception:
        return False


def is_relevant_job(position: str, description: str, tags: list[str]) -> bool:
    """Check if job is relevant for AI fresher/intern roles.

    Args:
        position: Job title
        description: Job description
        tags: Job tags

    Returns:
        True if job is relevant
    """
    text = f"{position} {description} {' '.join(tags)}".lower()
    return any(kw in text for kw in TARGET_KEYWORDS)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def fetch_url(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """Fetch URL content with retry logic.

    Args:
        client: HTTP client
        url: URL to fetch

    Returns:
        Response text or None on failure
    """
    config = get_config()

    if not is_allowed_domain(url):
        logger.warning(f"Blocked domain: {url}")
        return None

    try:
        response = await client.get(
            url,
            headers={"User-Agent": config.scraper.user_agent},
            timeout=30.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


async def discover_email_from_website(
    client: httpx.AsyncClient, company_website: str
) -> tuple[Optional[str], Optional[str], str]:
    """Discover contact email from company website.

    Args:
        client: HTTP client
        company_website: Company website URL

    Returns:
        Tuple of (email, source_url, contact_type)
    """
    config = get_config()

    if not company_website or not is_allowed_domain(company_website):
        return None, None, "UNKNOWN"

    # Try common paths
    for path in ALLOWED_PATHS:
        url = urljoin(company_website, path)
        await asyncio.sleep(config.scraper.rate_limit_seconds)

        content = await fetch_url(client, url)
        if not content:
            continue

        soup = BeautifulSoup(content, "html.parser")
        text = soup.get_text()

        emails = extract_emails_from_text(text)
        for email in emails:
            if is_valid_email_prefix(email):
                contact_type = "HR" if "hr" in email.lower() else "COMPANY"
                return email, url, contact_type

    return None, None, "UNKNOWN"


async def fetch_remoteok_jobs() -> list[dict]:
    """Fetch fresher/intern AI jobs from RemoteOK API.

    Returns:
        List of job dictionaries with emails only
    """
    config = get_config()
    jobs = []

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://remoteok.com/api",
                headers={"User-Agent": config.scraper.user_agent},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            # Skip first item (metadata)
            for item in data[1 : config.scraper.max_jobs_per_source + 1]:
                if not isinstance(item, dict):
                    continue

                position = item.get("position", "")
                description = item.get("description", "")
                tags = item.get("tags", [])

                # Filter for relevant AI/fresher roles
                if not is_relevant_job(position, description, tags):
                    continue

                # Create deterministic ID based on URL
                job_id = hashlib.sha256(item.get("url", "").encode()).hexdigest()[:8]
                if not job_id:
                    job_id = str(uuid.uuid4())

                job = {
                    "id": job_id,
                    "company": item.get("company", ""),
                    "role": position,
                    "description": description[:2000],
                    "job_url": item.get("url", ""),
                    "company_website": item.get("company_url", ""),
                    "location": item.get("location", "Remote"),
                    "source": "RemoteOK",
                    "contact_email": None,
                    "contact_type": "UNKNOWN",
                    "email_source_url": None,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                }
                jobs.append(job)

    except Exception as e:
        logger.error(f"RemoteOK fetch failed: {e}")

    return jobs


async def fetch_hn_jobs() -> list[dict]:
    """Fetch fresher/intern AI jobs from Hacker News 'Who is Hiring' API.

    Returns:
        List of job dictionaries with emails only
    """
    config = get_config()
    jobs = []

    try:
        async with httpx.AsyncClient() as client:
            # Get latest "Who is Hiring" post
            response = await client.get(
                "https://hacker-news.firebaseio.com/v0/user/whoishiring.json",
                timeout=30.0,
            )
            response.raise_for_status()
            user_data = response.json()

            if not user_data or "submitted" not in user_data:
                return jobs

            # Get most recent post
            post_id = user_data["submitted"][0]
            response = await client.get(
                f"https://hacker-news.firebaseio.com/v0/item/{post_id}.json",
                timeout=30.0,
            )
            response.raise_for_status()
            post = response.json()

            if not post or "kids" not in post:
                return jobs

            # Fetch job comments
            for kid_id in post["kids"][: config.scraper.max_jobs_per_source]:
                await asyncio.sleep(0.5)

                response = await client.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json",
                    timeout=30.0,
                )
                if response.status_code != 200:
                    continue

                comment = response.json()
                if not comment or comment.get("deleted"):
                    continue

                text = comment.get("text", "")
                if not text:
                    continue

                # Parse company and role from first line
                soup = BeautifulSoup(text, "html.parser")
                clean_text = soup.get_text()
                lines = clean_text.split("\n")
                first_line = lines[0] if lines else ""

                # Filter for relevant AI/fresher roles
                if not is_relevant_job(first_line, clean_text, []):
                    continue

                # Extract emails from text
                emails = extract_emails_from_text(clean_text)
                valid_email = None
                for email in emails:
                    if is_valid_email_prefix(email):
                        valid_email = email
                        break

                # ID based on HN item ID
                job_id = hashlib.sha256(f"hn_{kid_id}".encode()).hexdigest()[:8]

                job = {
                    "id": job_id,
                    "company": first_line.split("|")[0].strip()[:100],
                    "role": "AI/ML Engineer",
                    "description": clean_text[:2000],
                    "job_url": f"https://news.ycombinator.com/item?id={kid_id}",
                    "company_website": "",
                    "location": "Remote",
                    "source": "HackerNews",
                    "contact_email": valid_email,
                    "contact_type": "COMPANY" if valid_email else "UNKNOWN",
                    "email_source_url": (
                        f"https://news.ycombinator.com/item?id={kid_id}"
                        if valid_email
                        else None
                    ),
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                }
                jobs.append(job)

    except Exception as e:
        logger.error(f"HN fetch failed: {e}")

    return jobs


async def scrape_all_jobs() -> list[dict]:
    """Scrape fresher/intern AI jobs from all legal sources.

    Returns:
        Combined list of jobs with emails only
    """
    config = get_config()
    all_jobs = []

    logger.info("Starting fresher/intern AI job discovery from legal sources")

    # Fetch from sources concurrently
    results = await asyncio.gather(
        fetch_remoteok_jobs(),
        fetch_hn_jobs(),
        return_exceptions=True,
    )

    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Source failed: {result}")
        elif isinstance(result, list):
            all_jobs.extend(result)

    # Enrich jobs without emails from company websites
    async with httpx.AsyncClient() as client:
        for job in all_jobs:
            if not job["contact_email"] and job["company_website"]:
                await asyncio.sleep(config.scraper.rate_limit_seconds)
                email, source_url, contact_type = await discover_email_from_website(
                    client, job["company_website"]
                )
                if email:
                    job["contact_email"] = email
                    job["email_source_url"] = source_url
                    job["contact_type"] = contact_type

    # FILTER: Only keep jobs WITH emails
    jobs_with_email = [job for job in all_jobs if job["contact_email"]]

    logger.info(
        f"Discovered {len(all_jobs)} jobs total, "
        f"{len(jobs_with_email)} with emails (filtered)"
    )

    return jobs_with_email


def scrape_jobs(state: JobState) -> JobState:
    """LangGraph node: Discover fresher/intern AI jobs from legal sources.

    This is a synchronous wrapper for the async scraping logic.
    Only returns jobs with valid contact emails.

    Args:
        state: Current job state (typically empty for scraper)

    Returns:
        Updated state with job data
    """
    try:
        # Optimization: Check if job already exists locally
        req_id = state.get("job_id")
        jobs_file = DATA_DIR / "jobs.json"

        if req_id and jobs_file.exists():
            with open(jobs_file, "r") as f:
                existing_jobs = json.load(f)

            # Find requested job
            match = next((j for j in existing_jobs if j["id"].startswith(req_id)), None)
            if match:
                logger.info(f"Using existing job data for {match['id']}")
                return {
                    **state,
                    "job_id": match["id"],
                    "job_data": match,
                    "contact_email": match.get("contact_email"),
                    "contact_type": match.get("contact_type", "UNKNOWN"),
                    "email_source_url": match.get("email_source_url"),
                    "errors": state.get("errors", []),
                }

        # No match or no ID, proceed with scraping
        jobs = asyncio.run(scrape_all_jobs())

        # Save jobs to data file
        with open(jobs_file, "w") as f:
            json.dump(jobs, f, indent=2)

        for job in jobs:
            if job["id"] in existing_ids:
                continue
            if job.get("job_url") and job["job_url"] in existing_urls:
                continue
            new_unique_jobs.append(job)

        if new_unique_jobs:
            logger.info(f"Found {len(new_unique_jobs)} new unique jobs")
            # Append new jobs to existing
            all_jobs = existing_jobs + new_unique_jobs

            # Save updated list
            with open(jobs_file, "w") as f:
                json.dump(all_jobs, f, indent=2)

            for job in new_unique_jobs:
                log_activity(
                    "DISCOVERED",
                    job["id"],
                    job["company"],
                    f"{job['role']} ({job['contact_email']})",
                )

            logger.info(f"Saved {len(all_jobs)} total jobs to {jobs_file}")

            # Use the first NEW job as the selected one, or fall back to last added
            selected_job = new_unique_jobs[0]
        else:
            logger.info("No new unique jobs found")
            # If no new jobs, reuse the most recent one if available
            if existing_jobs:
                all_jobs = existing_jobs
                selected_job = existing_jobs[-1]
                # We still want to return a valid state to process maybe?
                # Or if the user really wants NEW jobs, we might skip.
                # For now, let's allow re-processing the last one if nothing new found,
                # UNLESS the user specifically asked for a new scrape.
                # But to avoid infinite loops of re-applying, let's just pick the last one
                # and let the pipeline decide (it likely checks 'sent' status elsewhere).

                # Actually, better to just return the filtered list of "jobs" (the new ones)
                # as the operating set for this run.
            else:
                all_jobs = existing_jobs
                return {
                    **state,
                    "errors": state.get("errors", []) + ["No jobs with emails found"],
                    "should_skip": True,
                    "skip_reason": "No jobs with emails discovered",
                }

        # Return state with the selected job
        # Check if a specific job_id was requested
        req_id = state.get("job_id")

        if req_id:
            # Find the requested job in the ALL list
            match = next((j for j in all_jobs if j["id"].startswith(req_id)), None)
            if match:
                selected_job = match
            else:
                logger.warning(f"Requested job {req_id} not found in scrape results.")

            return {
                **state,
                "job_id": selected_job["id"],
                "job_data": selected_job,
                "contact_email": selected_job.get("contact_email"),
                "contact_type": selected_job.get("contact_type", "UNKNOWN"),
                "email_source_url": selected_job.get("email_source_url"),
                "errors": state.get("errors", []),
            }
        else:
            return {
                **state,
                "errors": state.get("errors", []) + ["No jobs with emails found"],
                "should_skip": True,
                "skip_reason": "No jobs with emails discovered",
            }

    except Exception as e:
        logger.exception("Job scraping failed")
        return {
            **state,
            "errors": state.get("errors", []) + [str(e)],
            "should_skip": True,
            "skip_reason": f"Scraper error: {e}",
        }
