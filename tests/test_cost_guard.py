"""
Test cost guard module.
Verify: execution stops after MAX_LLM_CALLS_PER_RUN, warning logged.
"""

import pytest

from app.config import Config, LLMCallCounter, llm_counter


class TestCostGuard:
    """Test suite for cost guard."""

    def test_counter_starts_at_zero(self):
        """Verify counter starts at zero."""
        counter = LLMCallCounter()
        assert counter.count == 0

    def test_increment_increases_count(self):
        """Verify increment increases count."""
        counter = LLMCallCounter()
        counter.increment()
        assert counter.count == 1

    def test_can_call_returns_true_below_limit(self):
        """Verify can_call returns True below limit."""
        counter = LLMCallCounter()
        counter.max_calls = 25
        counter.count = 10
        
        assert counter.can_call() is True

    def test_can_call_returns_false_at_limit(self):
        """Verify can_call returns False at limit."""
        counter = LLMCallCounter()
        counter.max_calls = 25
        counter.count = 25
        
        assert counter.can_call() is False

    def test_can_call_returns_false_above_limit(self):
        """Verify can_call returns False above limit."""
        counter = LLMCallCounter()
        counter.max_calls = 25
        counter.count = 100
        
        assert counter.can_call() is False

    def test_increment_returns_false_when_exceeded(self):
        """Verify increment returns False when limit exceeded."""
        counter = LLMCallCounter()
        counter.max_calls = 2
        
        assert counter.increment() is True  # count = 1
        assert counter.increment() is True  # count = 2
        assert counter.increment() is False  # count = 3, exceeded

    def test_reset_clears_count(self):
        """Verify reset clears the count."""
        counter = LLMCallCounter()
        counter.count = 50
        counter.reset()
        
        assert counter.count == 0

    def test_max_calls_from_config(self):
        """Verify max_calls comes from config."""
        counter = LLMCallCounter()
        assert counter.max_calls == Config.MAX_LLM_CALLS_PER_RUN

    def test_global_counter_shared(self):
        """Verify global counter is shared across imports."""
        from app.config import llm_counter as counter1
        from app.config import llm_counter as counter2
        
        counter1.count = 42
        assert counter2.count == 42
        
        # Reset for other tests
        counter1.reset()

    def test_resume_builder_respects_limit(self, tmp_path, monkeypatch):
        """Verify resume builder respects LLM limit."""
        from app.resume_builder import ResumeBuilder
        
        monkeypatch.setattr(Config, "CRON_MODE", False)
        
        # Exhaust limit
        llm_counter.max_calls = 25
        llm_counter.count = 100
        
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text('[{"id": "test", "company": "A", "role": "B"}]')
        monkeypatch.setattr(Config, "JOBS_JSON", jobs_file)
        monkeypatch.setattr(Config, "RESUMES_CACHE", tmp_path)
        monkeypatch.setattr(Config, "COMPILED_RESUME_DIR", tmp_path)
        
        builder = ResumeBuilder()
        result = builder.tailor_resume("test")
        
        assert result is None, "Resume generated despite limit"
        
        # Reset
        llm_counter.reset()

    def test_email_generator_respects_limit(self, tmp_path, monkeypatch):
        """Verify email generator respects LLM limit."""
        from app.email_generator import EmailGenerator
        
        monkeypatch.setattr(Config, "CRON_MODE", False)
        
        # Exhaust limit
        llm_counter.max_calls = 25
        llm_counter.count = 100
        
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text('[{"id": "test", "company": "A", "role": "B", "description": "C"}]')
        monkeypatch.setattr(Config, "JOBS_JSON", jobs_file)
        
        contacts_file = tmp_path / "contacts.json"
        contacts_file.write_text('[{"job_id": "test", "email": "test@test.com"}]')
        monkeypatch.setattr(Config, "CONTACTS_JSON", contacts_file)
        
        approvals_file = tmp_path / "approvals.json"
        approvals_file.write_text("[]")
        monkeypatch.setattr(Config, "APPROVALS_JSON", approvals_file)
        
        generator = EmailGenerator()
        result = generator.generate_email("test")
        
        assert result is None, "Email generated despite limit"
        
        # Reset
        llm_counter.reset()
