# Setup Guide

This document explains how to install, configure, and run the AutoJob Agent locally.

## Prerequisites

### Python Version

- Python 3.10 or higher required
- Python 3.11 recommended for best compatibility

### LaTeX Distribution

The resume node requires `pdflatex` to compile LaTeX to PDF.

**Ubuntu/Debian:**

```bash
sudo apt-get install texlive-latex-base texlive-fonts-recommended texlive-fonts-extra texlive-latex-extra
```

**Windows:**

Download and install one of:
- [MiKTeX](https://miktex.org/download)
- [TeX Live](https://tug.org/texlive/windows.html)

Ensure `pdflatex` is in your system PATH.

**macOS:**

```bash
brew install --cask mactex
```

Or download [MacTeX](https://tug.org/mactex/).

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/lakshayknows/autojob-agent.git
cd autojob-agent/job-agent
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Configuration

### Environment Variables

Copy the example file:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
# Required: Google Gemini API Key
GOOGLE_API_KEY=your_google_api_key_here

# LLM Configuration
LLM_MODEL=gemini-1.5-flash
LLM_TEMPERATURE=0.3

# SMTP Configuration (required for sending)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=your_email@gmail.com
SMTP_PASSWORD=your_app_password_here

# Cost Control
MAX_LLM_CALLS_PER_RUN=25
MAX_TOKENS_PER_RUN=100000

# Scraper Settings
RATE_LIMIT_SECONDS=2.0
MAX_JOBS_PER_SOURCE=25

# Mode Control
CRON_MODE=false
DEBUG=false
```

### Required Variables

| Variable | Description |
|----------|-------------|
| `GOOGLE_API_KEY` | Gemini API key from Google AI Studio |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SMTP_EMAIL` | - | Gmail address for sending |
| `SMTP_PASSWORD` | - | App password (not regular password) |
| `CRON_MODE` | `false` | Block LLM calls and sending |
| `MAX_LLM_CALLS_PER_RUN` | `25` | Cost limit per run |
| `RATE_LIMIT_SECONDS` | `2.0` | Delay between scraper requests |

### Getting API Keys

**Gemini API Key:**

1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Create a new API key
3. Copy to `GOOGLE_API_KEY`

**Gmail App Password:**

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable two-factor authentication
3. Generate an app password under "App passwords"
4. Copy to `SMTP_PASSWORD`

## Running the Application

### Basic Commands

```bash
# View help
python -m app.main --help

# Check system status
python -m app.main status

# Discover jobs from legal sources
python -m app.main discover

# List discovered jobs
python -m app.main list

# Process a specific job (generates resume and email)
python -m app.main process <job_id>

# View pending approvals
python -m app.main pending

# Approve an application
python -m app.main approve <job_id> --resume

# Reject an application
python -m app.main reject <job_id> --reason "Not a good fit"
```

### Debug Mode

```bash
python -m app.main --debug discover
```

Or set in `.env`:

```env
DEBUG=true
```

## Running in CRON_MODE

CRON_MODE allows scheduled job discovery without triggering LLM calls or sending emails.

### Enable CRON_MODE

```env
CRON_MODE=true
```

### What CRON_MODE Blocks

- RAG context retrieval
- Resume tailoring
- Email drafting
- Email sending

### What CRON_MODE Allows

- Job discovery
- Legal guard checks
- Job archiving

### Example Cron Job

```bash
# Run discovery daily at 9 AM
0 9 * * * cd /path/to/job-agent && CRON_MODE=true python -m app.main discover
```

## Building Docker Image

### Build

```bash
docker build -t job-agent .
```

### Run

```bash
# With .env file
docker run --env-file .env job-agent status

# With individual variables
docker run -e GOOGLE_API_KEY=xxx job-agent discover

# Interactive shell
docker run -it --env-file .env --entrypoint bash job-agent
```

### Docker Volumes

Mount data directory to persist state:

```bash
docker run -v $(pwd)/data:/app/data --env-file .env job-agent status
```

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_approval_flow.py -v

# With coverage
python -m pytest tests/ --cov=app
```

## Troubleshooting

### "pdflatex not found"

LaTeX is not installed or not in PATH. See Prerequisites.

### "GOOGLE_API_KEY environment variable is required"

Set the API key in `.env` or environment:

```bash
export GOOGLE_API_KEY=your_key_here
```

### "SMTP authentication failed"

- Use an app password, not your regular password
- Ensure 2FA is enabled on your email account
- Check SMTP server and port settings

### Tests fail with import errors

Ensure you're in the virtual environment:

```bash
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS
```

### ChromaDB import errors

ChromaDB is optional. The system falls back to simple keyword extraction if ChromaDB is unavailable.

## Directory Structure

After setup, your directory should look like:

```
job-agent/
├── .env                  # Your configuration
├── .venv/                # Virtual environment
├── app/                  # Application code
├── data/                 # Runtime data (created automatically)
│   ├── jobs.json         # Discovered jobs
│   ├── approvals.json    # Approval decisions
│   ├── sent_emails.json  # Sent email log
│   ├── archive.json      # Archived applications
│   └── logs/             # Application logs
├── docs/                 # Documentation
├── prompts/              # LLM prompts
├── resume/
│   ├── template.tex      # Your base resume
│   ├── base_resume.tex   # Resume for RAG
│   └── compiled/         # Generated PDFs
├── tests/                # Test suite
└── requirements.txt      # Dependencies
```
