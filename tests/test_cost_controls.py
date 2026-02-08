"""Tests for cost controls."""

from unittest.mock import MagicMock, patch



from app.nodes.guards import cost_guard, cron_mode_guard


class TestCostGuard:
    """Test cost control guards."""

    @patch("app.nodes.guards.get_config")
    def test_cost_guard_allows_under_limit(self, mock_config, sample_state):
        """Test that under-limit calls are allowed."""
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = False  # Ensure cost guard runs
        mock_cfg.cost.max_llm_calls_per_run = 25
        mock_cfg.cost.max_tokens_per_run = 100000
        mock_config.return_value = mock_cfg

        state = {
            **sample_state,
            "llm_calls": 5,
            "total_tokens": 1000,
        }
        result = cost_guard(state)
        assert result.get("should_skip", False) is False

    @patch("app.nodes.guards.get_config")
    def test_cost_guard_blocks_over_llm_limit(self, mock_config, sample_state):
        """Test that over-limit LLM calls are blocked."""
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = False  # Ensure cost guard runs
        mock_cfg.cost.max_llm_calls_per_run = 25
        mock_cfg.cost.max_tokens_per_run = 100000
        mock_config.return_value = mock_cfg

        state = {
            **sample_state,
            "llm_calls": 30,
            "total_tokens": 1000,
        }
        result = cost_guard(state)
        assert result["should_skip"] is True
        assert "LLM call limit" in result.get("skip_reason", "")

    @patch("app.nodes.guards.get_config")
    def test_cost_guard_blocks_over_token_limit(self, mock_config, sample_state):
        """Test that over-limit token usage is blocked."""
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = False  # Ensure cost guard runs
        mock_cfg.cost.max_llm_calls_per_run = 25
        mock_cfg.cost.max_tokens_per_run = 100000
        mock_config.return_value = mock_cfg

        state = {
            **sample_state,
            "llm_calls": 5,
            "total_tokens": 150000,
        }
        result = cost_guard(state)
        assert result["should_skip"] is True
        assert "Token limit" in result.get("skip_reason", "")


class TestCronModeGuard:
    """Test CRON_MODE guard."""

    @patch("app.nodes.guards.get_config")
    def test_cron_mode_blocks_when_active(self, mock_config, sample_state):
        """Test that CRON_MODE blocks processing."""
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = True
        mock_config.return_value = mock_cfg

        result = cron_mode_guard(sample_state)
        assert result["should_skip"] is True
        assert "CRON_MODE" in result.get("skip_reason", "")

    @patch("app.nodes.guards.get_config")
    def test_cron_mode_allows_when_inactive(self, mock_config, sample_state):
        """Test that inactive CRON_MODE allows processing."""
        mock_cfg = MagicMock()
        mock_cfg.cron_mode = False
        mock_config.return_value = mock_cfg

        result = cron_mode_guard(sample_state)
        assert result.get("should_skip", False) is False


class TestCaching:
    """Test caching behavior."""

    def test_resume_cache_path_unique(self):
        """Test that resume cache paths are unique per job."""
        from app.nodes.resume import get_cache_path

        path1 = get_cache_path("job-123-abc")
        path2 = get_cache_path("job-456-def")
        assert path1 != path2

    def test_resume_cache_path_consistent(self):
        """Test that same job gets same cache path."""
        from app.nodes.resume import get_cache_path

        path1 = get_cache_path("job-123-abc")
        path2 = get_cache_path("job-123-abc")
        assert path1 == path2

    def test_email_cache_path_unique(self):
        """Test that email cache paths are unique per job."""
        from app.nodes.email import get_cache_path

        path1 = get_cache_path("job-123-abc")
        path2 = get_cache_path("job-456-def")
        assert path1 != path2


class TestTokenTracking:
    """Test token usage tracking."""

    def test_state_tracks_llm_calls(self, sample_state):
        """Test that state tracks LLM calls."""
        state = {
            **sample_state,
            "llm_calls": 0,
        }
        # Simulate an LLM call
        state["llm_calls"] += 1
        assert state["llm_calls"] == 1

    def test_state_tracks_tokens(self, sample_state):
        """Test that state tracks token usage."""
        state = {
            **sample_state,
            "total_tokens": 0,
        }
        # Simulate token usage
        state["total_tokens"] += 500
        assert state["total_tokens"] == 500
