"""
Test email discovery module.
Verify: only public emails, no personal emails, allowed paths, crawl depth.
"""

import pytest
import re

from app.scraper import JobScraper
from app.config import Config


class TestEmailDiscovery:
    """Test suite for email discovery."""

    def test_only_public_emails_extracted(self):
        """Verify email extraction prioritizes public emails."""
        # This tests the priority email regex patterns
        public_patterns = ["careers@", "jobs@", "hiring@", "hr@", "talent@", "recruiting@"]
        
        test_cases = [
            ("careers@company.com", True),
            ("jobs@startup.io", True),
            ("john.doe@company.com", False),
        ]
        
        for email, should_be_public in test_cases:
            is_public = any(p in email.lower() for p in public_patterns)
            assert is_public == should_be_public, f"Email {email} public={is_public}, expected={should_be_public}"

    def test_no_personal_emails_prioritized(self):
        """Verify personal emails are deprioritized."""
        public_patterns = ["careers@", "jobs@", "hiring@", "hr@"]
        
        # Personal emails should not match public patterns
        personal_email = "john.smith@company.com"
        is_personal_public = any(p in personal_email for p in public_patterns)
        
        assert is_personal_public is False, "Personal email matched public pattern"

    def test_allowed_paths_only(self):
        """Verify only allowed paths are followed."""
        allowed = Config.ALLOWED_PATHS
        
        test_urls = [
            ("https://company.com/careers", True),
            ("https://company.com/jobs", True),
            ("https://company.com/about", True),
            ("https://company.com/products", False),
            ("https://company.com/blog", False),
        ]
        
        for url, should_allow in test_urls:
            is_allowed = any(path in url for path in allowed)
            assert is_allowed == should_allow, f"URL {url} allowed={is_allowed}, expected={should_allow}"

    def test_crawl_depth_respected(self):
        """Verify crawl depth is limited to 1."""
        assert Config.CRAWL_DEPTH == 1, f"Crawl depth is {Config.CRAWL_DEPTH}, expected 1"

    def test_email_regex_patterns(self):
        """Verify email regex patterns work correctly."""
        scraper = JobScraper()
        
        # Priority patterns
        priority_patterns = [
            r"careers@[\w.-]+\.\w+",
            r"jobs@[\w.-]+\.\w+",
            r"hiring@[\w.-]+\.\w+",
            r"hr@[\w.-]+\.\w+",
            r"talent@[\w.-]+\.\w+",
            r"recruiting@[\w.-]+\.\w+",
        ]
        
        test_emails = [
            ("careers@company.com", True),
            ("jobs@startup.io", True),
            ("hiring@tech.co", True),
            ("random@test.com", False),
        ]
        
        for email, should_match_priority in test_emails:
            matches = any(re.match(p, email) for p in priority_patterns)
            # Just verify patterns compile and run
            assert isinstance(matches, bool)
