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

```
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

CRON_MODE allows scheduled job discovery without risk of:

- Unexpected LLM costs
- Accidental email sending
- Unreviewed applications

### What Is Blocked

```python
if config.cron_mode:
    # RAG retrieval
    return {..., "should_skip": True}

if config.cron_mode:
    # Resume tailoring
    return {..., "should_skip": True}

if config.cron_mode:
    # Email drafting
    return {..., "should_skip": True}

if config.cron_mode:
    # Email sending
    return {..., "errors": [..., "CRON_MODE blocked send"]}
```

### What Is Allowed

- Job discovery from public APIs
- Legal guard checks
- Archiving

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

- Outlook: Microsoft Account > Security > App passwords
- Gmail: Google Account > Security > App passwords

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
