# Modifying the System

This document explains how to safely extend or modify the AutoJob Agent.

## Important: What NOT to Change

Before making changes, understand these critical constraints:

### Do Not Modify

1. **Approval Gate Logic**: The `interrupt_before=["approval"]` in `graph.py` is the human-in-the-loop guarantee. Never remove or bypass it.

2. **Send Guard Checks**: All five checks in `send_guard` are required:
   - Approval status
   - Contact email existence
   - Resume PDF existence
   - Not already sent
   - CRON_MODE check

3. **Blocked Domains List**: Do not add LinkedIn or other protected sites to allowed sources.

4. **State TypedDict**: All state fields must remain JSON-serializable. No complex objects.

5. **Word Limit Enforcement**: The `truncate_to_word_limit` function in `email.py` enforces the 200-word limit.

### Think Twice Before Changing

1. **Rate Limit Settings**: Lower values may trigger anti-scraping protections. Higher values may violate terms of service.

2. **Cost Limits**: Removing limits can lead to unexpected API charges.

3. **Email Prefix Validation**: Loosening restrictions may result in sending to inappropriate addresses.

## How to Add a New Job Source

### Step 1: Create Fetch Function

Add to `app/nodes/scraper.py`:

```python
async def fetch_newsite_jobs() -> list[dict]:
    """Fetch jobs from NewSite API.

    Returns:
        List of job dictionaries with emails only
    """
    config = get_config()
    jobs = []

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.newsite.com/jobs",
                headers={"User-Agent": config.scraper.user_agent},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            for item in data[:config.scraper.max_jobs_per_source]:
                # Check relevance
                if not is_relevant_job(
                    item.get("title", ""),
                    item.get("description", ""),
                    item.get("tags", []),
                ):
                    continue

                job = {
                    "id": generate_job_id(item.get("url", "")),
                    "company": item.get("company", ""),
                    "role": item.get("title", ""),
                    "description": item.get("description", "")[:2000],
                    "job_url": item.get("url", ""),
                    "company_website": item.get("company_url", ""),
                    "location": item.get("location", "Remote"),
                    "source": "NewSite",
                    "contact_email": None,
                    "contact_type": "UNKNOWN",
                    "email_source_url": None,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                }
                jobs.append(job)

    except Exception as e:
        logger.error(f"NewSite fetch failed: {e}")

    return jobs
```

### Step 2: Add to Scrape Function

In `scrape_all_jobs()`:

```python
results = await asyncio.gather(
    fetch_remoteok_jobs(),
    fetch_hn_jobs(),
    fetch_newsite_jobs(),  # Add here
    return_exceptions=True,
)
```

### Step 3: Add to Allowed Sources

In `app/nodes/guards.py`:

```python
allowed_sources = [
    "RemoteOK",
    "HackerNews",
    "GoogleJobs",
    "Indeed",
    "AngelList",
    "NewSite",  # Add here
]
```

### Step 4: Add Tests

In `tests/test_scraper.py`:

```python
def test_newsite_source_allowed():
    """Test NewSite is recognized source."""
    from app.nodes.guards import legal_guard
    state = {
        "job_data": {"source": "NewSite"},
        "errors": [],
    }
    result = legal_guard(state)
    assert result.get("legal_check_passed", False) is True
```

## How to Add a New LangGraph Node

### Step 1: Create Node Function

Create file `app/nodes/mynode.py`:

```python
"""My custom node."""

from app.config import get_config, get_logger
from app.state import JobState

logger = get_logger("mynode")


def my_node(state: JobState) -> JobState:
    """LangGraph node: Description of what this node does.

    Args:
        state: Current job state

    Returns:
        Updated state
    """
    config = get_config()

    # Check CRON_MODE if this node uses LLM
    if config.cron_mode:
        logger.info("CRON_MODE active - skipping my_node")
        return {
            **state,
            "should_skip": True,
            "skip_reason": "CRON_MODE active",
        }

    try:
        # Your logic here
        result = do_something(state)

        return {
            **state,
            "my_field": result,
        }

    except Exception as e:
        logger.exception("my_node failed")
        return {
            **state,
            "errors": state.get("errors", []) + [f"MyNode error: {e}"],
        }
```

### Step 2: Add to State Model

In `app/state.py`, add your new field:

```python
class JobState(TypedDict, total=False):
    # ... existing fields ...

    # My new field
    my_field: Optional[str]
```

### Step 3: Add to Graph

In `app/graph.py`:

```python
from app.nodes.mynode import my_node

# In create_graph():
workflow.add_node("my_node", my_node)

# Add edges
workflow.add_edge("previous_node", "my_node")
workflow.add_edge("my_node", "next_node")
```

### Step 4: Export from Package

In `app/nodes/__init__.py`:

```python
from app.nodes.mynode import my_node

__all__ = [
    # ... existing ...
    "my_node",
]
```

### Step 5: Add Tests

In `tests/test_mynode.py`:

```python
"""Tests for my_node."""

from app.nodes.mynode import my_node


class TestMyNode:
    """Test my_node functionality."""

    def test_my_node_basic(self, sample_state):
        """Test basic functionality."""
        result = my_node(sample_state)
        assert "my_field" in result
```

## How to Change Resume Logic

### Modifying the Prompt

Edit `prompts/resume_tailor.md`:

```markdown
# ROLE
You are a resume tailoring agent.

# OBJECTIVE
[Modify objectives here]

# CONSTRAINTS
[Add or modify constraints]
```

### Modifying the Code

In `app/nodes/resume.py`:

1. **Change prompt construction**: Modify the `ChatPromptTemplate` in `tailor_resume()`
2. **Add validation**: Add checks after LLM response
3. **Modify caching**: Change `get_cache_path()` if cache key needs updating

### Testing Changes

```bash
# Run with debug mode
python -m app.main --debug process <job_id>

# Check output
cat resume/compiled/resume_<job_id>.tex
```

## How to Adjust Cost Limits

### Via Environment

```env
MAX_LLM_CALLS_PER_RUN=50
MAX_TOKENS_PER_RUN=200000
```

### Via Code

In `app/config.py`:

```python
@dataclass
class CostConfig:
    max_llm_calls_per_run: int
    max_tokens_per_run: int = 100000
    cache_resume: bool = True
    cache_email: bool = True
```

### Monitoring Usage

Check state after processing:

```python
final_state = app.get_state(config)
print(f"LLM calls: {final_state.values.get('llm_calls')}")
print(f"Tokens: {final_state.values.get('total_tokens')}")
```

## How to Add a New Guard

### Step 1: Create Guard Function

In `app/nodes/guards.py`:

```python
def my_guard(state: JobState) -> JobState:
    """LangGraph node: My custom guard.

    Args:
        state: Current job state

    Returns:
        Updated state with validation result
    """
    errors = state.get("errors", [])

    # Check conditions
    if not my_condition(state):
        return {
            **state,
            "should_skip": True,
            "skip_reason": "My guard failed",
            "errors": errors + ["My guard: condition not met"],
        }

    return state


def route_after_my_guard(state: JobState) -> Literal["pass", "fail"]:
    """Route based on my guard result."""
    if state.get("should_skip", False):
        return "fail"
    return "pass"
```

### Step 2: Add to Graph

In `app/graph.py`:

```python
from app.nodes.guards import my_guard, route_after_my_guard

# In create_graph():
workflow.add_node("my_guard", my_guard)

workflow.add_conditional_edges(
    "my_guard",
    route_after_my_guard,
    {
        "pass": "next_node",
        "fail": "archive",
    },
)
```

### Step 3: Export and Test

Add to `__init__.py` and create tests.

## Adding New Email Prefixes

In `app/nodes/scraper.py` and `app/nodes/guards.py`:

```python
ALLOWED_EMAIL_PREFIXES = [
    "careers",
    "jobs",
    "hiring",
    "hr",
    "talent",
    "recruiting",
    "apply",
    "team",
    # Add new prefix here
]
```

## Checklist Before Committing

1. All tests pass: `python -m pytest tests/ -v`
2. No import errors: `python -c "from app.nodes import *"`
3. State is serializable: No complex objects in TypedDict
4. Guards are not bypassed
5. Approval gate is intact
6. Documentation updated
