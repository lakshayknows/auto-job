"""
Structured logging module for job automation system.
Non-verbose by default. Logs to console and errors.log.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

from app.config import Config


def setup_logging(verbose: bool = False) -> logging.Logger:
    """
    Set up structured logging.
    
    Args:
        verbose: If True, set DEBUG level. Otherwise INFO.
    
    Returns:
        Configured logger instance.
    """
    # Create logs directory
    logs_dir = Config.DATA_DIR
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger("job_agent")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Formatter with timestamp, module, level, message
    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler (INFO level, non-verbose)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Error file handler (ERROR level only)
    error_handler = logging.FileHandler(logs_dir / "errors.log", encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    return logger


# Global logger instance
logger = setup_logging()


# Leak detection flags
class LeakDetector:
    """Track potential cost leaks and safety violations."""
    
    def __init__(self):
        self.embedding_calls: dict[str, int] = {}
        self.resume_generations: dict[str, int] = {}
        self.email_generations: dict[str, int] = {}
        self.llm_calls_in_cron: int = 0
        self.unapproved_send_attempts: int = 0
    
    def log_embedding_call(self, content_hash: str) -> None:
        """Log embedding API call. Flag if duplicate."""
        if content_hash in self.embedding_calls:
            self.embedding_calls[content_hash] += 1
            logger.warning(f"LEAK: Duplicate embedding call for hash {content_hash[:8]}...")
        else:
            self.embedding_calls[content_hash] = 1
    
    def log_resume_generation(self, job_id: str, reason: str = "") -> None:
        """Log resume generation. Flag if regeneration without reason."""
        if job_id in self.resume_generations:
            if not reason:
                logger.warning(f"LEAK: Resume regeneration for {job_id} without reason")
            self.resume_generations[job_id] += 1
        else:
            self.resume_generations[job_id] = 1
    
    def log_email_generation(self, job_id: str, reason: str = "") -> None:
        """Log email generation. Flag if regeneration without request."""
        if job_id in self.email_generations:
            if not reason:
                logger.warning(f"LEAK: Email regeneration for {job_id} without request")
            self.email_generations[job_id] += 1
        else:
            self.email_generations[job_id] = 1
    
    def log_llm_call_in_cron(self) -> None:
        """Log LLM call during cron mode. Always a violation."""
        self.llm_calls_in_cron += 1
        logger.error(f"VIOLATION: LLM call attempted in CRON_MODE")
    
    def log_unapproved_send(self, draft_id: str) -> None:
        """Log send attempt without approval. Always a violation."""
        self.unapproved_send_attempts += 1
        logger.error(f"VIOLATION: Send attempt for unapproved draft {draft_id}")
    
    def get_summary(self) -> dict:
        """Get leak detection summary."""
        return {
            "duplicate_embeddings": sum(v - 1 for v in self.embedding_calls.values() if v > 1),
            "resume_regenerations": sum(v - 1 for v in self.resume_generations.values() if v > 1),
            "email_regenerations": sum(v - 1 for v in self.email_generations.values() if v > 1),
            "llm_calls_in_cron": self.llm_calls_in_cron,
            "unapproved_send_attempts": self.unapproved_send_attempts,
        }


# Global leak detector instance
leak_detector = LeakDetector()
