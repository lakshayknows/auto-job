"""Configuration and environment management for AutoJob Agent."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RESUME_DIR = BASE_DIR / "resume"
RAG_INDEX_DIR = BASE_DIR / "rag_index"
PROMPTS_DIR = BASE_DIR / "prompts"
LOGS_DIR = DATA_DIR / "logs"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
(RESUME_DIR / "compiled").mkdir(parents=True, exist_ok=True)
RAG_INDEX_DIR.mkdir(exist_ok=True)


@dataclass
class LLMConfig:
    """LLM configuration settings."""

    google_api_key: str
    model_name: str = "gemini-1.5-flash"
    temperature: float = 0.3
    max_output_tokens: int = 4096


@dataclass
class SMTPConfig:
    """SMTP email configuration."""

    server: str
    port: int
    email: str
    password: str
    use_tls: bool = True


@dataclass
class CostConfig:
    """Cost control settings."""

    max_llm_calls_per_run: int
    max_tokens_per_run: int = 100000
    cache_resume: bool = True
    cache_email: bool = True


@dataclass
class ScraperConfig:
    """Scraper settings."""

    rate_limit_seconds: float = 2.0
    max_jobs_per_source: int = 25
    max_crawl_depth: int = 1
    user_agent: str = "AutoJobAgent/2.0 (Educational Project)"
    serpapi_key: Optional[str] = None


@dataclass
class Config:
    """Main configuration container."""

    llm: LLMConfig
    smtp: SMTPConfig
    cost: CostConfig
    scraper: ScraperConfig
    cron_mode: bool = False
    debug: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables.

        Returns:
            Config instance with values from environment

        Raises:
            ValueError: If required environment variables are missing
        """
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")

        return cls(
            llm=LLMConfig(
                google_api_key=google_api_key,
                model_name=os.getenv("LLM_MODEL", "gemini-1.5-flash"),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            ),
            smtp=SMTPConfig(
                server=os.getenv("SMTP_SERVER", "smtp.office365.com"),
                port=int(os.getenv("SMTP_PORT", "587")),
                email=os.getenv("SMTP_EMAIL", ""),
                password=os.getenv("SMTP_PASSWORD", ""),
            ),
            cost=CostConfig(
                max_llm_calls_per_run=int(os.getenv("MAX_LLM_CALLS_PER_RUN", "25")),
                max_tokens_per_run=int(os.getenv("MAX_TOKENS_PER_RUN", "100000")),
            ),
            scraper=ScraperConfig(
                rate_limit_seconds=float(os.getenv("RATE_LIMIT_SECONDS", "2.0")),
                max_jobs_per_source=int(os.getenv("MAX_JOBS_PER_SOURCE", "25")),
                serpapi_key=os.getenv("SERPAPI_KEY"),
            ),
            cron_mode=os.getenv("CRON_MODE", "false").lower() == "true",
            debug=os.getenv("DEBUG", "false").lower() == "true",
        )


def setup_logging(config: Optional[Config] = None) -> logging.Logger:
    """Configure logging for the application.

    Args:
        config: Optional config to determine debug level

    Returns:
        Configured logger instance
    """
    log_level = logging.DEBUG if (config and config.debug) else logging.INFO

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOGS_DIR / "autojob.log"),
        ],
    )

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)

    return logging.getLogger("autojob")


# Global config instance (lazy loaded)
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance.

    Returns:
        Config instance
    """
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def get_logger(name: str = "autojob") -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
