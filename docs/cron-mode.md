# CRON_MODE Documentation

This document explains the CRON_MODE safety mechanism in AutoJob Agent.

## What is CRON_MODE?

CRON_MODE is a **hard safety boundary** that enables safe, scheduled job discovery.

When `CRON_MODE=true`:
- The system operates in **read-only discovery mode**
- Jobs are scraped from public APIs
- Emails are extracted from public career pages
- All data is saved locally to `data/jobs.json`
- **No LLM calls, resume generation, email drafting, or sending occurs**

## What CRON_MODE is NOT

CRON_MODE is NOT:
- A "soft preference" that can be overridden
- A mode that allows "some" LLM usage
- A way to run the full pipeline on a schedule
- Compatible with job processing commands

## Allowed Operations

| Operation | Description |
|-----------|-------------|
| Job scraping | Fetching from RemoteOK, HackerNews APIs |
| Email discovery | Crawling public career/contact pages |
| Data persistence | Writing to `data/jobs.json` |
| Logging | Recording discovery activity |
| `discover` command | CLI job discovery |
| `list` command | CLI job listing (read-only) |
| `status` command | CLI status display (read-only) |

## Blocked Operations

| Operation | Error Raised |
|-----------|--------------|
| RAG retrieval | `CronModeError("RAG retrieval")` |
| Resume tailoring | `CronModeError("resume tailoring")` |
| Email drafting | `CronModeError("email drafting")` |
| Email sending | `CronModeError("email sending")` |
| `process` command | CLI error before execution |
| `approve` command | CLI error before execution |
| `reject` command | CLI error before execution |
| Cost guard evaluation | Explicitly disabled (no LLM = no cost) |

## Why Email Discovery is Allowed

Email discovery is allowed because it:
- Uses only read-only HTTP requests
- Accesses only public career/contact pages
- Does not invoke any LLM
- Does not send any data externally
- Is purely local data enrichment

The mental model: **if it's read-only and deterministic, it's allowed**.

## How CRON_MODE is Enforced

CRON_MODE enforcement happens at **three levels**:

### 1. CLI Level (First Line of Defense)

```python
# In main.py
CRON_ALLOWED_COMMANDS = {"discover", "list", "status"}

if config.cron_mode and args.command not in CRON_ALLOWED_COMMANDS:
    print("❌ CRON_MODE is active - only discover, list, status commands are allowed")
    sys.exit(1)
```

### 2. Graph Level (Routing Guard)

```python
# In graph.py - check_cron_mode node
if is_cron_mode():
    return {
        **state,
        "should_skip": True,
        "skip_reason": "CRON_MODE active - LLM blocked",
    }
```

### 3. Node Level (Hard Circuit Breaker)

```python
# In each LLM-using node
def retrieve_context(state):
    assert_not_cron_mode("RAG retrieval")  # Raises CronModeError
    ...
```

## CronModeError Exception

When a blocked operation is attempted, `CronModeError` is raised:

```python
class CronModeError(RuntimeError):
    def __init__(self, operation: str):
        self.operation = operation
        super().__init__(f"CRON_MODE active - blocked operation: {operation}")
```

This exception:
- Immediately halts execution
- Clearly identifies the blocked operation
- Is caught and displayed at CLI level
- Cannot be silently ignored

## Enabling CRON_MODE

### Environment Variable

```bash
export CRON_MODE=true
```

### Inline with Command

```bash
CRON_MODE=true python -m app.main discover
```

### In .env File

```env
CRON_MODE=true
```

### Windows PowerShell

```powershell
$env:CRON_MODE="true"; python -m app.main discover
```

## Verifying CRON_MODE is Active

1. **Check CLI Output**

   ```
   CRON_MODE: 🔴 Active
   ```

2. **Check Logs**

   ```
   CRON_MODE active - blocking LLM operations
   ```

3. **Attempt Blocked Command**

   ```bash
   CRON_MODE=true python -m app.main process abc123
   # Output: ❌ CRON_MODE is active - only discover, list, status commands are allowed
   ```

## Scheduled Job Setup

### Linux/macOS (Cron)

```cron
# Run discovery every 6 hours
0 */6 * * * CRON_MODE=true /path/to/python -m app.main discover
```

### Windows (Task Scheduler)

```
Program: cmd.exe
Arguments: /c "set CRON_MODE=true && cd C:\path\to\job-agent && python -m app.main discover"
```

See `cron_job.example` in the repository for detailed examples.

## Testing CRON_MODE

Run the dedicated test suite:

```bash
python -m pytest tests/test_cron_mode.py -v
```

Tests verify:
- All blocked operations raise `CronModeError`
- Allowed operations complete successfully
- Cost guard is explicitly disabled
- No LLM instantiation occurs
- CLI enforcement works correctly

## Design Rationale

The CRON_MODE design follows these principles:

1. **Fail-Safe by Default**: Blocked operations raise exceptions, not silent skips
2. **Defense in Depth**: Three enforcement levels (CLI, graph, node)
3. **Explicit over Implicit**: Guards check `is_cron_mode()` explicitly
4. **Zero Cost Risk**: Cost guards disabled (no LLM = no cost tracking)
5. **Auditable**: All blocks are logged with clear messages

## Troubleshooting

### "CRON_MODE blocked operation" Error

**Cause**: Attempting a blocked operation while CRON_MODE is active.

**Solution**: Set `CRON_MODE=false` or use only allowed commands.

### Jobs Not Being Discovered

**Cause**: Network issues or API rate limiting.

**Solution**: Check logs in `data/logs/autojob.log` for HTTP errors.

### Cost Guard Still Evaluating

**Cause**: Outdated code without CRON_MODE check in cost_guard.

**Solution**: Update to latest version with explicit CRON_MODE check.

## Related Documentation

- [How It Works](how-it-works.md) - Full pipeline explanation
- [Security and Compliance](security-and-compliance.md) - Safety guarantees
- [Architecture](architecture.md) - System design
