# AutoJob Agent

A LangGraph-powered automated job application system that discovers jobs, tailors resumes, drafts emails, and sends applications with human-in-the-loop approval.

## Features

- **Job Discovery**: Scrapes legal public sources (RemoteOK, Hacker News)
- **Email Extraction**: Discovers public company contact emails
- **RAG-Powered Tailoring**: Uses vector search to match resume to job requirements
- **Resume Generation**: Tailors LaTeX resumes for specific roles
- **Email Drafting**: Generates professional cold emails (≤200 words)
- **Human Approval**: LangGraph interrupt mechanism for review before sending
- **SMTP Integration**: Sends emails via Outlook with resume attachment

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Scraper   │────▶│ Legal Guard  │────▶│     RAG     │
└─────────────┘     └──────────────┘     └─────────────┘
                                                │
                    ┌──────────────┐     ┌──────▼──────┐
                    │   Approval   │◀────│   Resume    │
                    │  (Interrupt) │     │   Tailor    │
                    └──────────────┘     └─────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Approved │ │ Rejected │ │ Pending  │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │            │            │
             ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐    (Wait)
        │  Send    │ │ Archive  │
        │  Guard   │ └──────────┘
        └────┬─────┘
             │
             ▼
        ┌──────────┐
        │   SMTP   │
        │   Send   │
        └──────────┘
```

## Quick Start

### 1. Setup Environment

```bash
# Clone repository
git clone https://github.com/lakshayknows/autojob-agent.git
cd autojob-agent

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys
```

### 2. Configure API Keys

Edit `.env`:
```
GOOGLE_API_KEY=your_gemini_api_key
SMTP_EMAIL=your_email@outlook.com
SMTP_PASSWORD=your_app_password
```

### 3. Run Commands

```bash
# Discover jobs from legal sources
python -m app.main discover

# List discovered jobs
python -m app.main list

# Process a specific job
python -m app.main process <job_id>

# View pending approvals
python -m app.main pending

# Approve an application
python -m app.main approve <job_id> --resume

# Reject an application
python -m app.main reject <job_id> --reason "Not a good fit"

# Check status
python -m app.main status
```

## Project Structure

```
job-agent/
├── app/
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   ├── state.py           # State model (TypedDict)
│   ├── graph.py           # LangGraph workflow
│   ├── main.py            # CLI entrypoint
│   └── nodes/
│       ├── scraper.py     # Job discovery
│       ├── guards.py      # Legal/send guards
│       ├── rag.py         # RAG context retrieval
│       ├── resume.py      # Resume tailoring
│       ├── email.py       # Email drafting
│       ├── approval.py    # Human approval
│       └── sender.py      # SMTP sending
├── prompts/               # LLM prompt files
├── resume/
│   ├── base_resume.tex    # Your base resume
│   └── compiled/          # Generated PDFs
├── data/                  # Runtime data
├── tests/                 # Test suite
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Safety Features

### Legal Compliance
- ✅ No LinkedIn scraping
- ✅ No personal profile scraping
- ✅ Respect robots.txt
- ✅ Rate-limited HTTP calls
- ✅ Public APIs only

### Human-in-the-Loop
- ✅ Approval required before sending
- ✅ All decisions logged
- ✅ CRON_MODE blocks LLM and sending

### Cost Control
- ✅ LLM call limits
- ✅ Token usage tracking
- ✅ Resume/email caching
- ✅ Skip if outputs exist

## Development

### Run Tests

```bash
pytest tests/ -v
```

### Code Quality

```bash
# Format code
black app/ tests/
isort app/ tests/

# Lint
flake8 app/ tests/

# Security scan
bandit -r app -ll

# Dependency audit
pip-audit
```

### Docker

```bash
# Build image
docker build -t job-agent .

# Run container
docker run --env-file .env job-agent status
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | Yes | - | Gemini API key |
| `SMTP_EMAIL` | No | - | Outlook email address |
| `SMTP_PASSWORD` | No | - | Outlook app password |
| `CRON_MODE` | No | `false` | Block LLM/sending |
| `MAX_LLM_CALLS_PER_RUN` | No | `25` | Cost limit |
| `RATE_LIMIT_SECONDS` | No | `2.0` | Scraper delay |

## License

MIT
