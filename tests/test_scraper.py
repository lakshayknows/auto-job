"""Tests for scraper node."""

import pytest

from app.nodes.scraper import (
    extract_emails_from_text,
    is_allowed_domain,
    is_valid_email_prefix,
)


class TestEmailExtraction:
    """Test email extraction functions."""

    def test_extract_emails_basic(self):
        """Test basic email extraction."""
        text = "Contact us at careers@example.com for opportunities"
        emails = extract_emails_from_text(text)
        assert "careers@example.com" in emails

    def test_extract_multiple_emails(self):
        """Test extracting multiple emails."""
        text = """
        HR: hr@company.com
        Jobs: jobs@company.com
        """
        emails = extract_emails_from_text(text)
        assert len(emails) == 2
        assert "hr@company.com" in emails
        assert "jobs@company.com" in emails

    def test_extract_no_emails(self):
        """Test text with no emails."""
        text = "No emails here, just text."
        emails = extract_emails_from_text(text)
        assert len(emails) == 0


class TestEmailValidation:
    """Test email prefix validation."""

    def test_valid_careers_email(self):
        """Test careers@ email is valid."""
        assert is_valid_email_prefix("careers@example.com") is True

    def test_valid_jobs_email(self):
        """Test jobs@ email is valid."""
        assert is_valid_email_prefix("jobs@example.com") is True

    def test_valid_hr_email(self):
        """Test hr@ email is valid."""
        assert is_valid_email_prefix("hr@example.com") is True

    def test_valid_hiring_email(self):
        """Test hiring@ email is valid."""
        assert is_valid_email_prefix("hiring@example.com") is True

    def test_invalid_personal_email(self):
        """Test personal email is invalid."""
        assert is_valid_email_prefix("john@example.com") is False

    def test_invalid_random_email(self):
        """Test random email is invalid."""
        assert is_valid_email_prefix("random123@example.com") is False


class TestDomainValidation:
    """Test domain validation."""

    def test_allowed_domain(self):
        """Test allowed domain."""
        assert is_allowed_domain("https://example.com/careers") is True

    def test_blocked_linkedin(self):
        """Test LinkedIn is blocked."""
        assert is_allowed_domain("https://linkedin.com/in/user") is False

    def test_blocked_facebook(self):
        """Test Facebook is blocked."""
        assert is_allowed_domain("https://facebook.com/company") is False

    def test_blocked_twitter(self):
        """Test Twitter is blocked."""
        assert is_allowed_domain("https://twitter.com/user") is False

    def test_allowed_company_site(self):
        """Test company site is allowed."""
        assert is_allowed_domain("https://tech-company.io/jobs") is True
