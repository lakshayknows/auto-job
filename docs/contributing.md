# Contributing to AutoJob Agent

Thank you for your interest in contributing to AutoJob Agent. This document provides guidelines and best practices for contributing to this project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Testing Requirements](#testing-requirements)
- [Code Style](#code-style)
- [Documentation](#documentation)
- [Issue Guidelines](#issue-guidelines)

---

## Code of Conduct

### Our Standards

- Be respectful and inclusive
- Accept constructive criticism gracefully
- Focus on what is best for the project
- Show empathy towards other contributors

### Unacceptable Behavior

- Harassment or discrimination
- Trolling or insulting comments
- Publishing others' private information
- Other conduct inappropriate for a professional setting

---

## Getting Started

### Understanding the Codebase

Before contributing, familiarize yourself with:

1. [Architecture Documentation](architecture.md) - System design and node structure
2. [How It Works](how-it-works.md) - Step-by-step workflow explanation
3. [Modification Guide](modifying-the-system.md) - Safe extension patterns

### Finding Issues to Work On

- Look for issues labeled `good first issue` or `help wanted`
- Check the [Roadmap](#roadmap) section in README for planned features
- Ask in issues before starting large changes

---

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- LaTeX distribution (for resume tests)

### Local Setup

```bash
# 1. Fork the repository on GitHub

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/autojob-agent.git
cd autojob-agent/job-agent

# 3. Add upstream remote
git remote add upstream https://github.com/lakshayknows/autojob-agent.git

# 4. Create virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

# 5. Install dependencies
pip install -r requirements.txt

# 6. Install development dependencies
pip install black isort flake8 pytest pytest-cov

# 7. Copy environment file
cp .env.example .env
# Add a test API key (required for some tests)
```

### Verify Setup

```bash
# Run tests
python -m pytest tests/ -v

# Check formatting
black --check app/ tests/
isort --check app/ tests/

# Lint
flake8 app/ tests/
```

---

## Making Changes

### Branch Naming

Use descriptive branch names:

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feature/description` | `feature/add-indeed-source` |
| Bug fix | `fix/description` | `fix/email-word-count` |
| Documentation | `docs/description` | `docs/update-setup-guide` |
| Refactor | `refactor/description` | `refactor/scraper-async` |

### Commit Messages

Follow conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**

```
feat(scraper): add Indeed job source

- Implement fetch_indeed_jobs() async function
- Add Indeed to allowed sources in guards.py
- Add tests for Indeed source validation

Closes #42
```

```
fix(email): enforce 200 word limit correctly

The truncate_to_word_limit function was counting characters
instead of words. Fixed to use split() for accurate count.

Fixes #37
```

### Keep Changes Focused

- One feature or fix per pull request
- Avoid mixing unrelated changes
- Keep commits atomic and reversible

---

## Pull Request Process

### Before Submitting

1. **Sync with upstream**

```bash
git fetch upstream
git rebase upstream/main
```

2. **Run all tests**

```bash
python -m pytest tests/ -v
```

3. **Format code**

```bash
black app/ tests/
isort app/ tests/
```

4. **Lint**

```bash
flake8 app/ tests/
```

5. **Update documentation** if needed

### PR Template

When creating a pull request, include:

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring

## Testing
- [ ] All existing tests pass
- [ ] Added new tests for changes
- [ ] Tested manually

## Checklist
- [ ] Code follows project style
- [ ] Self-reviewed code
- [ ] Updated documentation
- [ ] No breaking changes

## Related Issues
Closes #XX
```

### Review Process

1. Maintainers will review within 3-5 business days
2. Address feedback in new commits (don't force push during review)
3. Once approved, maintainers will merge
4. Delete your branch after merge

---

## Testing Requirements

### All Changes Must Include Tests

- New features need corresponding test cases
- Bug fixes need regression tests
- Aim for test coverage of new code

### Test Structure

```python
"""Tests for my_feature."""

import pytest
from app.nodes.my_feature import my_function


class TestMyFeature:
    """Test my_feature functionality."""

    def test_basic_case(self, sample_state):
        """Test basic functionality."""
        result = my_function(sample_state)
        assert result["expected_field"] == expected_value

    def test_edge_case(self, sample_state):
        """Test edge case handling."""
        state = {**sample_state, "edge_field": edge_value}
        result = my_function(state)
        assert result.get("error") is None

    def test_error_handling(self, sample_state):
        """Test error handling."""
        state = {**sample_state, "bad_field": bad_value}
        result = my_function(state)
        assert "error" in result.get("errors", [])
```

### Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific file
python -m pytest tests/test_scraper.py -v

# With coverage
python -m pytest tests/ --cov=app --cov-report=term-missing

# Stop on first failure
python -m pytest tests/ -x
```

### Test Fixtures

Use fixtures from `conftest.py`:

- `sample_job`: Sample job dictionary
- `sample_state`: Complete JobState for testing

---

## Code Style

### Python Style

- Follow PEP 8
- Use Black for formatting (line length 88)
- Use isort for import sorting
- Use type hints for function signatures

### Formatting Commands

```bash
# Format code
black app/ tests/

# Sort imports
isort app/ tests/

# Check without modifying
black --check app/ tests/
isort --check app/ tests/
```

### Docstrings

Use Google-style docstrings:

```python
def my_function(state: JobState, option: str = "default") -> JobState:
    """Brief description of function.

    Longer description if needed, explaining what the function
    does and any important details.

    Args:
        state: Current job state
        option: Description of option

    Returns:
        Updated state with new fields

    Raises:
        ValueError: If option is invalid
    """
    pass
```

### Import Order

```python
# Standard library
import json
import os
from pathlib import Path

# Third-party
import httpx
from langchain_core.prompts import ChatPromptTemplate

# Local
from app.config import get_config, get_logger
from app.state import JobState
```

---

## Documentation

### When to Update Docs

- Adding new features
- Changing existing behavior
- Adding new configuration options
- Modifying CLI commands

### Documentation Files

| File | Update When |
|------|-------------|
| `README.md` | Major features, CLI changes |
| `docs/architecture.md` | Graph structure, node changes |
| `docs/how-it-works.md` | Workflow changes |
| `docs/setup.md` | Dependencies, configuration |
| `docs/demos.md` | New CLI examples |
| `docs/modifying-the-system.md` | Extension patterns |
| `docs/security-and-compliance.md` | Security changes |

### Documentation Style

- Clear, concise language
- No marketing speak
- Include code examples
- Use tables for structured data
- Keep lines under 100 characters

---

## Issue Guidelines

### Bug Reports

Include:

1. **Description**: What happened?
2. **Expected**: What should have happened?
3. **Steps to Reproduce**: How can we replicate it?
4. **Environment**: Python version, OS, dependencies
5. **Logs**: Relevant error messages

### Feature Requests

Include:

1. **Problem**: What problem does this solve?
2. **Proposed Solution**: How would it work?
3. **Alternatives**: Other approaches considered
4. **Impact**: Who benefits from this?

### Security Issues

**Do NOT open public issues for security vulnerabilities.**

Email security concerns directly to maintainers with:

- Description of vulnerability
- Steps to reproduce
- Potential impact

---

## Critical Constraints

When contributing, these constraints must be maintained:

### Never Modify

1. **Approval Gate**: `interrupt_before=["approval"]` in `graph.py`
2. **Send Guard Checks**: All 5 checks must remain
3. **Blocked Domains**: LinkedIn and other protected sites
4. **Word Limit**: 200-word email limit enforcement

### Always Maintain

1. **State Serializability**: Only JSON-compatible types
2. **Test Coverage**: All tests must pass
3. **Documentation**: Update docs for changes
4. **Logging**: Log important actions

See [modifying-the-system.md](modifying-the-system.md) for details.

---

## Questions?

- Open an issue for general questions
- Check existing issues and documentation first
- Be specific about what you're trying to accomplish

Thank you for contributing to AutoJob Agent!
