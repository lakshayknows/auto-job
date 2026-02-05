# AutoJob Agent

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-40%20passed-brightgreen)
![LangGraph](https://img.shields.io/badge/LangGraph-2.0-purple)

**A LangGraph-powered autonomous job application agent with human-in-the-loop approval.**

[Architecture](#architecture) | [Quick Start](#quick-start) | [Documentation](#documentation) | [Contributing](#contributing)

</div>

---

## Overview

AutoJob Agent is an automated job application system that discovers entry-level AI/ML jobs from legal public sources, tailors your resume for each role, drafts personalized cold emails, and sends them with your explicit approval.

### Key Features

- **Autonomous Job Discovery**: Scrapes legal public APIs (RemoteOK, Hacker News "Who is Hiring")
- **Smart Email Extraction**: Discovers public company emails from career pages
- **RAG-Powered Tailoring**: Uses vector search to match your resume to job requirements
- **LaTeX Resume Generation**: Produces professional, single-page tailored resumes
- **Intelligent Email Drafting**: Generates concise cold emails (max 200 words)
- **Human-in-the-Loop**: Graph pauses for your approval before sending anything
- **Cost Controls**: Token limits, LLM call limits, and aggressive caching
- **Safety First**: No LinkedIn scraping, no auto-sending, full audit trail

### What This Is NOT

- A job board aggregator
- A spam tool
- A way to bypass application tracking systems
- A LinkedIn automation tool (explicitly blocked)

---

## Architecture

AutoJob Agent is built on [LangGraph](https://github.com/langchain-ai/langgraph), a framework for building stateful, multi-step AI workflows with explicit control flow.

```
                    START
                      │
                      ▼
               ┌───────────┐
               │  Scraper  │  ← Discover jobs from legal sources
               └─────┬─────┘
                     │
                     ▼
              ┌─────────────┐
              │ Legal Guard │  ← Block disallowed domains
              └──────┬──────┘
                     │
            ┌────────┴────────┐
            ▼                 ▼
       ┌─────────┐       ┌─────────┐
       │  Pass   │       │  Fail   │
       └────┬────┘       └────┬────┘
            │                 │
            ▼                 │
      ┌───────────┐           │
      │Source Guard│  ← Validate email prefix
      └─────┬─────┘           │
            │                 │
            ▼                 │
      ┌───────────┐           │
      │CRON Check │  ← Block LLM in CRON_MODE
      └─────┬─────┘           │
            │                 │
       ┌────┴────┐            │
       ▼         ▼            │
   ┌───────┐ ┌───────┐        │
   │  RAG  │ │ Skip  │────────┤
   └───┬───┘ └───────┘        │
       │                      │
       ▼                      │
   ┌────────┐                 │
   │ Resume │  ← Tailor LaTeX resume
   └───┬────┘                 │
       │                      │
       ▼                      │
   ┌───────┐                  │
   │ Email │  ← Draft cold email
   └───┬───┘                  │
       │                      │
       ▼                      │
   ┌──────────┐               │
   │ APPROVAL │  ← ⏸️ Human reviews here
   └────┬─────┘               │
        │                     │
   ┌────┼────────────┐        │
   ▼    ▼            ▼        │
APPROVED REJECTED  PENDING    │
   │       │         │        │
   ▼       │         ▼        │
┌──────┐   │      (wait)      │
│ Send │   │                  │
│Guard │   │                  │
└──┬───┘   │                  │
   │       │                  │
   ▼       ▼                  ▼
┌────────┐ ┌────────┐    ┌────────┐
│ Sender │ │Archive │    │Archive │
└───┬────┘ └────────┘    └────────┘
    │
    ▼
┌────────┐
│Archive │
└───┬────┘
    │
    ▼
   END
```

### Why LangGraph?

| Requirement | LangGraph Solution |
|-------------|-------------------|
| Explicit state management | TypedDict state model |
| Human-in-the-loop | `interrupt_before` mechanism |
| Conditional routing | `add_conditional_edges` |
| State persistence | `MemorySaver` checkpointing |
| Auditability | Every transition is logged |

See [docs/architecture.md](docs/architecture.md) for detailed design documentation.

---

## Quick Start

### Prerequisites

- **Python 3.10+** (3.11 recommended)
- **LaTeX distribution** for resume compilation:
  - Ubuntu: `sudo apt-get install texlive-latex-base texlive-fonts-recommended`
  - Windows: [MiKTeX](https://miktex.org/download) or [TeX Live](https://tug.org/texlive/)
  - macOS: [MacTeX](https://tug.org/mactex/)

### Installation

```bash
# Clone the repository
git clone https://github.com/lakshayknows/autojob-agent.git
cd autojob-agent/job-agent

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### Configuration

Edit `.env` with your credentials:

```env
# Required
GOOGLE_API_KEY=your_gemini_api_key

# Optional: For sending emails
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=your_email@gmail.com
SMTP_PASSWORD=your_app_password
```

Get your Gemini API key from [Google AI Studio](https://aistudio.google.com/).

### Your First Run

```bash
# 1. Check system status
python -m app.main status

# 2. Discover jobs from legal sources
python -m app.main discover

# 3. List discovered jobs
python -m app.main list

# 4. Process a specific job (generates resume + email)
python -m app.main process <job_id>

# 5. Review the generated artifacts:
#    - Resume: resume/compiled/resume_<job_id>.pdf
#    - Email: data/email_draft_<job_id>.json

# 6. Approve and send
python -m app.main approve <job_id> --resume

# Or reject
python -m app.main reject <job_id> --reason "Not a good fit"
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `status` | Show system status (jobs, pending, sent) |
| `discover` | Discover jobs from legal sources |
| `list [--limit N]` | List discovered jobs |
| `process <job_id>` | Process job (RAG + resume + email) |
| `pending` | List pending approvals |
| `approve <job_id> [--notes] [--resume]` | Approve and optionally resume processing |
| `reject <job_id> [--reason]` | Reject application |

### Global Options

| Option | Description |
|--------|-------------|
| `--debug` | Enable debug logging |
| `--help` | Show help message |

---

## Project Structure

```
job-agent/
├── app/                      # Application code
│   ├── __init__.py
│   ├── config.py             # Configuration management
│   ├── state.py              # State model (TypedDict)
│   ├── graph.py              # LangGraph workflow definition
│   ├── main.py               # CLI entrypoint
│   └── nodes/                # LangGraph nodes
│       ├── approval.py       # Human approval interrupt
│       ├── email.py          # Email drafting
│       ├── guards.py         # Legal, source, send guards
│       ├── rag.py            # RAG context retrieval
│       ├── resume.py         # Resume tailoring
│       ├── scraper.py        # Job discovery
│       └── sender.py         # SMTP sending
│
├── data/                     # Runtime data (gitignored)
│   ├── jobs.json             # Discovered jobs
│   ├── approvals.json        # Approval decisions
│   ├── sent_emails.json      # Sent email log
│   ├── archive.json          # Archived applications
│   ├── activity.csv          # Activity timeline
│   └── logs/                 # Application logs
│
├── docs/                     # Documentation
│   ├── architecture.md       # System design
│   ├── how-it-works.md       # Detailed walkthrough
│   ├── setup.md              # Setup guide
│   ├── demos.md              # Examples and demos
│   ├── modifying-the-system.md  # Extension guide
│   ├── security-and-compliance.md  # Security docs
│   └── contributing.md       # Contribution guide
│
├── prompts/                  # LLM prompt specifications
│   ├── email_writer.md
│   ├── resume_tailor.md
│   └── ...
│
├── resume/                   # Resume assets
│   ├── template.tex          # Your base resume
│   ├── base_resume.tex       # Resume for RAG
│   └── compiled/             # Generated PDFs
│
├── tests/                    # Test suite
│   ├── test_approval_flow.py
│   ├── test_cost_controls.py
│   ├── test_email_guard.py
│   └── test_scraper.py
│
├── .env.example              # Environment template
├── Dockerfile                # Container build
├── requirements.txt          # Python dependencies
└── pyproject.toml            # Project configuration
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | System design, state model, approval mechanism |
| [How It Works](docs/how-it-works.md) | Step-by-step walkthrough of all nodes |
| [Setup Guide](docs/setup.md) | Installation, configuration, Docker |
| [Demos](docs/demos.md) | CLI examples and sample outputs |
| [Modification Guide](docs/modifying-the-system.md) | How to extend safely |
| [Security & Compliance](docs/security-and-compliance.md) | Legal scraping, data handling |
| [Contributing](docs/contributing.md) | How to contribute |

---

## Safety Features

### Legal Compliance

| Feature | Implementation |
|---------|---------------|
| No LinkedIn scraping | Domain explicitly blocked |
| No personal profiles | Only career pages accessed |
| Rate limiting | 2+ second delay between requests |
| Robots.txt respect | Limited to known public APIs |
| Transparent user-agent | `AutoJobAgent/2.0 (Educational Project)` |

### Human-in-the-Loop

| Feature | Implementation |
|---------|---------------|
| Approval required | Graph interrupts at approval node |
| No auto-sending | Send guard requires `APPROVED` status |
| Review artifacts | Resume and email saved before approval |
| Decision logging | All approvals/rejections timestamped |

### Cost Control

| Feature | Implementation |
|---------|---------------|
| LLM call limits | Default 25 calls per run |
| Token limits | Default 100k tokens per run |
| Aggressive caching | Resume and email cached per job_id |
| CRON_MODE | Blocks all LLM calls and sending |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | Yes | - | Gemini API key |
| `SMTP_EMAIL` | No | - | Email address for sending |
| `SMTP_PASSWORD` | No | - | Email app password |
| `SMTP_SERVER` | No | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | No | `587` | SMTP port |
| `CRON_MODE` | No | `false` | Block LLM and sending |
| `MAX_LLM_CALLS_PER_RUN` | No | `25` | Cost limit |
| `MAX_TOKENS_PER_RUN` | No | `100000` | Token limit |
| `RATE_LIMIT_SECONDS` | No | `2.0` | Scraper delay |
| `DEBUG` | No | `false` | Enable debug logging |

---

## Docker

### Build

```bash
docker build -t autojob-agent .
```

### Run

```bash
# With env file
docker run --env-file .env autojob-agent status

# With mounted data directory
docker run -v $(pwd)/data:/app/data --env-file .env autojob-agent discover
```

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=app --cov-report=html

# Run specific test file
python -m pytest tests/test_approval_flow.py -v
```

Current test coverage: **40 tests passing**

---

## Contributing

We welcome contributions! Please see [docs/contributing.md](docs/contributing.md) for:

- Code of conduct
- Development setup
- Pull request process
- Testing requirements
- Code style guidelines

### Quick Contribution Checklist

- [ ] Fork the repository
- [ ] Create a feature branch
- [ ] Write tests for new functionality
- [ ] Ensure all 40+ tests pass
- [ ] Update documentation if needed
- [ ] Submit pull request

---

## Roadmap

### Planned Features

- [ ] Additional job sources (AngelList, Indeed API)
- [ ] Web UI for approval workflow
- [ ] Email template customization
- [ ] Multi-resume support
- [ ] Application tracking dashboard

### Not Planned

- LinkedIn integration (legal concerns)
- Auto-approval mode (defeats purpose)
- Mass email sending (spam concerns)

---

## Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) - Workflow orchestration
- [LangChain](https://github.com/langchain-ai/langchain) - LLM utilities
- [Google Gemini](https://ai.google.dev/) - LLM provider
- [ChromaDB](https://www.trychroma.com/) - Vector database

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

## Disclaimer

This tool is for educational and personal use. Users are responsible for:

- Complying with terms of service of scraped websites
- Ensuring emails are appropriate and professional
- Not using this tool for spam or harassment
- Reviewing all content before sending

The authors are not responsible for misuse of this software.

---

<div align="center">

**Built with LangGraph**

[Report Bug](https://github.com/lakshayknows/autojob-agent/issues) · [Request Feature](https://github.com/lakshayknows/autojob-agent/issues) · [Documentation](docs/)

</div>
