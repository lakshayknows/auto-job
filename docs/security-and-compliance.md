# Security and Compliance

This document explains the security measures, legal compliance, and safety guarantees built into the AutoJob Agent.

## Legal Scraping Rules

### Allowed Sources

The system only accesses publicly available data from these sources:

| Source | Type | Data Accessed |
|--------|------|---------------|
| RemoteOK | Public API | Job listings JSON |
| Hacker News | Public API | "Who is Hiring" posts |
| Company Websites | Public pages | Career pages, contact info |

### Disallowed Sources

The following sources are explicitly blocked:

| Source | Reason |
|--------|--------|
| LinkedIn | Terms of service violation, legal risk |
| Facebook | Personal data concerns |
| Twitter/X | Terms of service |
| Instagram | Not job-related, personal data |

### Implementation

Blocked domains are hardcoded in `app/nodes/scraper.py` and `app/nodes/guards.py`:

```python
BLOCKED_DOMAINS = [
    "linkedin.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
]
```

Every URL is checked before access:

```python
def is_allowed_domain(url: str) -> bool:
    domain = urlparse(url).netloc.lower()
    return not any(blocked in domain for blocked in BLOCKED_DOMAINS)
```

### Crawl Constraints

1. **robots.txt**: Respected by limiting to known public APIs and career pages
2. **Rate Limiting**: Minimum 2-second delay between requests
3. **Depth Limit**: Maximum crawl depth of 1 (no deep crawling)
4. **Path Restrictions**: Only allowed paths are accessed:
   - `/careers`
   - `/jobs`
   - `/join-us`
   - `/about`
   - `/contact`
   - `/work`
   - `/team`

5. **User-Agent**: Identifies as `AutoJobAgent/2.0 (Educational Project)`

## Email Safety

### Allowed Email Prefixes

Only company/HR emails are allowed:

| Prefix | Type |
|--------|------|
| `careers@` | Company |
| `jobs@` | Company |
| `hiring@` | Company |
| `hr@` | HR |
| `talent@` | HR |
| `recruiting@` | HR |
| `apply@` | Company |
| `team@` | Company |

### Personal Email Handling

Personal emails (e.g., `john@company.com`) are only allowed if:

1. Explicitly listed as HR/hiring contact on the company website
2. `contact_type` is set to `HR`

Otherwise, personal emails are rejected by the source guard.

### No Email Fabrication

The system never:

- Guesses email patterns (e.g., firstname.lastname@company.com)
- Generates emails from scraped names
- Uses email finder services
- Accesses email databases

If no valid email is found, the `contact_email` field is set to `null`.

## Human-in-the-Loop Guarantees

### Approval Gate

The approval mechanism is enforced at three levels:

1. **Graph Level**: `interrupt_before=["approval"]` pauses execution
2. **Route Level**: `route_after_approval()` returns `"pending"` for unapproved jobs
3. **Send Level**: `send_guard()` checks `approval_status == "APPROVED"`

### Approval Flow

```text
[Email Drafted] --> [Approval Node] --> INTERRUPT
                                            |
                                    [Human Reviews]
                                            |
                         +------------------+------------------+
                         |                  |                  |
                      APPROVE            REJECT             (No Action)
                         |                  |                  |
                         v                  v                  v
                   [Send Guard]        [Archive]           [Pending]
```

### No Auto-Approval

There is no mechanism for automatic approval. Each job requires:

1. Human runs `approve` or `reject` command
2. Decision is logged to `data/approvals.json`
3. Graph resumes only after human action

### Audit Trail

All decisions are logged:

- `data/approvals.json`: Approval status with timestamp
- `data/activity.csv`: Event log with timestamps
- `data/logs/autojob.log`: Detailed execution log

## Data Storage Boundaries

### What Is Stored

| Data | Location | Contents |
|------|----------|----------|
| Jobs | `data/jobs.json` | Public job listings |
| Approvals | `data/approvals.json` | User decisions |
| Sent Emails | `data/sent_emails.json` | Send confirmations |
| Archive | `data/archive.json` | Final job states |
| Activity | `data/activity.csv` | Event timeline |
| Logs | `data/logs/autojob.log` | Execution logs |
| Resumes | `resume/compiled/` | Generated PDFs |
| Drafts | `data/email_draft_*.json` | Email drafts |

### What Is NOT Stored

- Passwords (only loaded from environment)
- API keys (only loaded from environment)
- Personal information beyond what's in the user's resume
- Scraped HTML pages (only extracted data)
- Cookies or session tokens

### Data Retention

All data is local. No data is sent to external services except:

1. Gemini API for LLM calls (prompts and resume content)
2. SMTP server for sending emails
3. ChromaDB embeddings API (if enabled)

## Why LinkedIn Is Not Scraped

### Legal Risk

LinkedIn has actively pursued legal action against scrapers:

- hiQ Labs v. LinkedIn (ongoing litigation)
- Cease and desist letters to scraping services
- Terms of service explicitly prohibit scraping

### Technical Blocks

LinkedIn employs:

- Login walls
- Rate limiting
- Bot detection
- CAPTCHAs

### Ethical Concerns

LinkedIn profiles contain personal information that individuals may not have intended to be scraped by automated systems.

### Alternative Approach

Instead of scraping LinkedIn:

1. Use public job boards with open APIs
2. Scrape company career pages (public by design)
3. Accept that some jobs will not have discoverable emails

## Auditability Guarantees

### Traceability

Every job application can be traced:

1. **Discovery**: `data/activity.csv` logs when job was found
2. **Processing**: `data/logs/autojob.log` records each step
3. **Artifacts**: Resume and email drafts are saved per job
4. **Decision**: `data/approvals.json` records approval/rejection
5. **Sending**: `data/sent_emails.json` confirms delivery

### Reproducibility

Given the same inputs:

1. Job discovery is deterministic (same source data = same jobs)
2. RAG retrieval is deterministic (same embeddings)
3. LLM outputs are cached per job_id (same output on rerun)

### Verification

All outputs can be verified:

1. Resume LaTeX can be manually reviewed before compilation
2. Email drafts are stored as JSON for review
3. Sent emails are logged with recipient and timestamp

## CRON_MODE Safety

### Purpose

CRON_MODE is a **hard safety boundary** that enables scheduled job discovery without risk of:

- Unexpected LLM costs
- Accidental email sending
- Unreviewed applications

### Enforcement Levels

CRON_MODE is enforced at **three levels**:

| Level | Location | Mechanism |
|-------|----------|-----------|
| CLI | `main.py` | Blocks non-allowed commands before execution |
| Graph | `graph.py` | Routes to archive, bypasses LLM nodes |
| Node | Each LLM node | Raises `CronModeError` (hard circuit breaker) |

### Hard Circuit Breaker

Each LLM-using node has a hard circuit breaker:

```python
def retrieve_context(state):
    assert_not_cron_mode("RAG retrieval")  # Raises CronModeError
    ...
```

This ensures violations are impossible to ignore.

### What Is Allowed

| Operation | Reason |
|-----------|--------|
| Job scraping | Read-only HTTP, no LLM |
| Email discovery | Read-only HTTP, no LLM |
| Writing jobs.json | Local data persistence |
| Legal/source guards | No LLM |
| Archiving | No LLM |
| `discover` command | Allowed at CLI |
| `list` command | Read-only, allowed at CLI |
| `status` command | Read-only, allowed at CLI |

### What Is Blocked

| Operation | Exception Raised |
|-----------|------------------|
| RAG retrieval | `CronModeError("RAG retrieval")` |
| Resume tailoring | `CronModeError("resume tailoring")` |
| Email drafting | `CronModeError("email drafting")` |
| Email sending | `CronModeError("email sending")` |
| `process` command | CLI blocks before execution |
| `approve` command | CLI blocks before execution |
| `reject` command | CLI blocks before execution |
| Cost guard | Explicitly disabled (no LLM = no cost) |

### Why Email Discovery Is Allowed

Email discovery is allowed in CRON_MODE because it:

1. Uses only read-only HTTP requests
2. Accesses only public career/contact pages
3. Does not invoke any LLM
4. Does not send any data externally
5. Is purely local data enrichment

The mental model: **if it's read-only and deterministic, it's allowed**.

> See [CRON_MODE Documentation](cron-mode.md) for complete details.

## Cost Protection

### LLM Call Limits

```python
if llm_calls >= config.cost.max_llm_calls_per_run:
    return {..., "should_skip": True}
```

### Token Limits

```python
if total_tokens >= config.cost.max_tokens_per_run:
    return {..., "should_skip": True}
```

### Caching

Cached outputs prevent redundant LLM calls:

- Resume: `resume/compiled/resume_{job_id}.tex`
- Email: `data/email_draft_{job_id}.json`

## Security Best Practices

### Environment Variables

Never commit `.env` to version control:

```gitignore
.env
.env.local
```

### App Passwords

Use app passwords, not account passwords:

- Gmail: Google Account > Security > App passwords
- Outlook: Microsoft Account > Security > App passwords

### API Key Rotation

Rotate API keys periodically:

1. Generate new key in Google AI Studio
2. Update `.env` file
3. Revoke old key

### Container Security

When using Docker:

```bash
# Do not embed secrets in image
docker build -t job-agent .

# Pass secrets at runtime
docker run --env-file .env job-agent
```

## MCP Weaponization Prevention

This system implements multiple safeguards to prevent autonomous or malicious use as an "MCP weapon":

### Human-in-the-Loop Enforcement

All outbound actions require explicit human approval:

| Action | Autonomous? | Approval Required |
|--------|-------------|-------------------|
| Job Discovery | ✅ Yes | ❌ No |
| Resume Generation | ✅ Yes | ❌ No (local only) |
| Email Drafting | ✅ Yes | ❌ No (draft only) |
| **Email Sending** | ❌ No | ✅ **YES** |

### Approval Mechanisms

1. **Interactive CLI Prompt**: When processing a job, the CLI prompts for `[y/n]` confirmation
2. **Separate Approve Command**: `python -m app.main approve <job_id>` requires explicit invocation
3. **State Verification**: `send_guard` validates `approval_status == APPROVED` before dispatch

### Design Decisions

> [!IMPORTANT]
> The approval requirement is **intentional and cannot be bypassed programmatically**.

This design ensures:
- No autonomous mass emailing
- Human review of every outbound message
- Clear audit trail of approvals
- Prevention of spam or phishing attacks

### Runtime Guards

```python
# In send_guard()
if state.get("approval_status") != "APPROVED":
    return {..., "send_guard_passed": False, "errors": ["Not approved"]}
```

### CRON_MODE Protection

When `CRON_MODE=true`:
- All LLM calls are blocked
- All email sending is blocked
- Only read-only operations are allowed

This prevents scheduled jobs from autonomously sending emails.

