"""
Job scraper module for collecting job listings from public sources.
Follows RALPH prompt guidelines for ethical scraping.
"""

import csv
import json
import random
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.config import Config


class JobScraper:
    """
    Autonomous job-collection agent.
    
    Scrapes up to 100 job listings per run with:
    - Company name
    - Role title
    - Full job description
    - Company website
    - Job URL
    - Publicly listed hiring emails (careers@, hiring@, jobs@, hr@)
    
    LIMITS:
    - DO NOT scrape LinkedIn profiles or private data
    - DO NOT guess emails
    - ONLY extract emails visible on company-owned public pages
    - Skip companies without public emails
    """

    # Email patterns to prioritize
    EMAIL_PATTERNS = [
        r"careers@[\w.-]+\.\w+",
        r"jobs@[\w.-]+\.\w+",
        r"hiring@[\w.-]+\.\w+",
        r"hr@[\w.-]+\.\w+",
        r"recruit(?:ing|ment)?@[\w.-]+\.\w+",
        r"talent@[\w.-]+\.\w+",
    ]

    # Generic email pattern
    GENERIC_EMAIL_PATTERN = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

    # User agent for polite scraping
    USER_AGENT = (
        "JobSearchBot/1.0 (Personal job search automation; "
        "contact: connect.lakshay@outlook.com)"
    )

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})
        self.jobs: list[dict] = []
        self.contacts: list[dict] = []
        Config.ensure_directories()

    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        time.sleep(random.uniform(1, 3))

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a web page."""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def _extract_emails_from_text(self, text: str) -> list[str]:
        """Extract email addresses from text, prioritizing hiring-related emails."""
        emails = set()

        # First, try to find prioritized email patterns
        for pattern in self.EMAIL_PATTERNS:
            found = re.findall(pattern, text, re.IGNORECASE)
            emails.update(found)

        # If no priority emails found, try generic pattern
        if not emails:
            found = re.findall(self.GENERIC_EMAIL_PATTERN, text)
            # Filter out common non-hiring emails
            for email in found:
                email_lower = email.lower()
                if not any(
                    skip in email_lower
                    for skip in ["support@", "info@", "sales@", "noreply@", "help@"]
                ):
                    emails.add(email)

        return list(emails)

    def _discover_public_email(self, company_website: str) -> Optional[dict]:
        """
        Crawl company website to discover public hiring emails.
        Only crawls allowed paths with depth limit of 1.
        """
        if not company_website:
            return None

        parsed = urlparse(company_website)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # Pages to check
        pages_to_check = [company_website]
        for path in Config.ALLOWED_PATHS:
            pages_to_check.append(urljoin(base_url, path))

        all_text = ""
        source_url = None

        for url in pages_to_check:
            self._rate_limit()
            soup = self._fetch_page(url)
            if soup:
                all_text += soup.get_text() + " "
                if source_url is None:
                    source_url = url

        emails = self._extract_emails_from_text(all_text)

        if emails:
            # Return the first (highest priority) email found
            return {"email": emails[0], "source": source_url or company_website}

        return None

    def scrape_remoteok(self) -> list[dict]:
        """Scrape jobs from RemoteOK API."""
        print("Scraping RemoteOK...")
        jobs = []

        try:
            response = self.session.get(
                "https://remoteok.com/api",
                headers={"Accept": "application/json"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            # Skip the first item (it's metadata)
            for item in data[1 : Config.MAX_JOBS_PER_RUN + 1]:
                if len(jobs) >= Config.MAX_JOBS_PER_RUN:
                    break

                job = {
                    "id": str(uuid.uuid4()),
                    "company": item.get("company", ""),
                    "role": item.get("position", ""),
                    "description": item.get("description", ""),
                    "url": item.get("url", ""),
                    "company_website": item.get("company_logo", "").split("/")[2]
                    if item.get("company_logo")
                    else "",
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "source": "remoteok",
                }

                # Try to construct company website
                if job["company"]:
                    company_slug = job["company"].lower().replace(" ", "")
                    job["company_website"] = f"https://{company_slug}.com"

                if job["company"] and job["role"]:
                    jobs.append(job)

        except Exception as e:
            print(f"Error scraping RemoteOK: {e}")

        return jobs

    def scrape_greenhouse_jobs(self, company_boards: list[str]) -> list[dict]:
        """
        Scrape jobs from Greenhouse-hosted ATS pages.
        company_boards: list of company board IDs (e.g., ['figma', 'stripe'])
        """
        jobs = []

        for board_id in company_boards:
            if len(jobs) >= Config.MAX_JOBS_PER_RUN:
                break

            print(f"Scraping Greenhouse board: {board_id}")
            self._rate_limit()

            try:
                api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_id}/jobs"
                response = self.session.get(api_url, timeout=30)
                response.raise_for_status()
                data = response.json()

                for job_data in data.get("jobs", []):
                    if len(jobs) >= Config.MAX_JOBS_PER_RUN:
                        break

                    # Fetch full job description
                    job_url = f"{api_url}/{job_data['id']}"
                    self._rate_limit()
                    job_response = self.session.get(job_url, timeout=30)

                    if job_response.ok:
                        full_job = job_response.json()
                        description = BeautifulSoup(
                            full_job.get("content", ""), "html.parser"
                        ).get_text()
                    else:
                        description = ""

                    job = {
                        "id": str(uuid.uuid4()),
                        "company": board_id.title(),
                        "role": job_data.get("title", ""),
                        "description": description,
                        "url": job_data.get("absolute_url", ""),
                        "company_website": f"https://{board_id}.com",
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "source": "greenhouse",
                    }

                    if job["role"]:
                        jobs.append(job)

            except Exception as e:
                print(f"Error scraping Greenhouse board {board_id}: {e}")

        return jobs

    def scrape_lever_jobs(self, company_boards: list[str]) -> list[dict]:
        """
        Scrape jobs from Lever-hosted ATS pages.
        company_boards: list of company slugs (e.g., ['netflix', 'spotify'])
        """
        jobs = []

        for company in company_boards:
            if len(jobs) >= Config.MAX_JOBS_PER_RUN:
                break

            print(f"Scraping Lever board: {company}")
            self._rate_limit()

            try:
                api_url = f"https://api.lever.co/v0/postings/{company}"
                response = self.session.get(api_url, timeout=30)
                response.raise_for_status()
                data = response.json()

                for job_data in data:
                    if len(jobs) >= Config.MAX_JOBS_PER_RUN:
                        break

                    description_parts = []
                    for section in job_data.get("lists", []):
                        description_parts.append(section.get("text", ""))
                        description_parts.extend(section.get("content", ""))

                    description = (
                        job_data.get("descriptionPlain", "")
                        + "\n"
                        + "\n".join(description_parts)
                    )

                    job = {
                        "id": str(uuid.uuid4()),
                        "company": company.title(),
                        "role": job_data.get("text", ""),
                        "description": description,
                        "url": job_data.get("hostedUrl", ""),
                        "company_website": f"https://{company}.com",
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "source": "lever",
                    }

                    if job["role"]:
                        jobs.append(job)

            except Exception as e:
                print(f"Error scraping Lever board {company}: {e}")

        return jobs

    def discover_emails_for_jobs(self) -> None:
        """Discover public emails for all scraped jobs."""
        print("Discovering public emails...")

        for job in self.jobs:
            if not job.get("company_website"):
                continue

            email_info = self._discover_public_email(job["company_website"])
            if email_info:
                contact = {
                    "job_id": job["id"],
                    "company": job["company"],
                    "email": email_info["email"],
                    "source": email_info["source"],
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                }
                self.contacts.append(contact)
                print(f"  Found email for {job['company']}: {email_info['email']}")

    def _save_to_json(self, data: list[dict], filepath: Path) -> None:
        """Save data to JSON file."""
        existing = []
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    existing = json.load(f)
                except json.JSONDecodeError:
                    existing = []

        # Merge with existing data (avoid duplicates by id)
        existing_ids = {item.get("id") or item.get("job_id") for item in existing}
        for item in data:
            item_id = item.get("id") or item.get("job_id")
            if item_id not in existing_ids:
                existing.append(item)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    def _save_to_csv(self, data: list[dict], filepath: Path) -> None:
        """Save data to CSV file."""
        if not data:
            return

        # Get all unique keys
        all_keys = set()
        for item in data:
            all_keys.update(item.keys())
        fieldnames = sorted(all_keys)

        # Load existing data
        existing = []
        existing_ids = set()
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing.append(row)
                    existing_ids.add(row.get("id") or row.get("job_id"))

        # Merge new data
        for item in data:
            item_id = item.get("id") or item.get("job_id")
            if item_id not in existing_ids:
                existing.append(item)

        # Write all data
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(existing)

    def save_results(self) -> None:
        """Save scraped jobs and contacts to JSON and CSV files."""
        print(f"Saving {len(self.jobs)} jobs and {len(self.contacts)} contacts...")

        # Save jobs
        self._save_to_json(self.jobs, Config.JOBS_JSON)
        self._save_to_csv(self.jobs, Config.JOBS_CSV)

        # Save contacts
        self._save_to_json(self.contacts, Config.CONTACTS_JSON)
        self._save_to_csv(self.contacts, Config.CONTACTS_CSV)

        print("Results saved successfully.")

    def run(
        self,
        greenhouse_boards: Optional[list[str]] = None,
        lever_boards: Optional[list[str]] = None,
    ) -> None:
        """
        Run the full scraping pipeline.
        
        Args:
            greenhouse_boards: List of Greenhouse board IDs to scrape
            lever_boards: List of Lever company slugs to scrape
        """
        print("Starting job scraper...")

        # Default boards to scrape (can be customized)
        if greenhouse_boards is None:
            greenhouse_boards = []

        if lever_boards is None:
            lever_boards = []

        # Scrape RemoteOK
        self.jobs.extend(self.scrape_remoteok())

        # Scrape Greenhouse boards
        if greenhouse_boards:
            self.jobs.extend(self.scrape_greenhouse_jobs(greenhouse_boards))

        # Scrape Lever boards
        if lever_boards:
            self.jobs.extend(self.scrape_lever_jobs(lever_boards))

        # Limit to max jobs
        self.jobs = self.jobs[: Config.MAX_JOBS_PER_RUN]

        print(f"Scraped {len(self.jobs)} jobs total.")

        # Discover emails
        self.discover_emails_for_jobs()

        # Save results
        self.save_results()

        print("Scraping complete!")


def main():
    """Entry point for scraper module."""
    scraper = JobScraper()
    scraper.run()


if __name__ == "__main__":
    main()
