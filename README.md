# Job Automation System

A production-grade, legal, and approval-gated job automation system that scrapes job listings, tailors resumes using RAG, drafts personalized cold emails, and sends only after explicit human approval.

## Features

- **Legal Scraping**: Only scrapes public job boards (RemoteOK, Greenhouse, Lever ATS)
- **Public Email Discovery**: Extracts only publicly visible hiring emails (careers@, jobs@, hiring@, hr@)
- **RAG-Powered Personalization**: Uses LangChain + Google Gemini for context-aware generation
- **LaTeX Resumes**: Generates tailored `.tex` files compiled to PDF via pdflatex
- **Approval Gate**: Tri-state approval system (PENDING/APPROVED/REJECTED) - no auto-sending
- **Cost Optimization**: Hash-based caching, lazy loading, configurable LLM call limits
- **Docker + Cron**: Automated weekly scraping (cron never triggers sending)

## Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/lakshayknows/auto-job.git
cd auto-job
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required environment variables:
```
GOOGLE_API_KEY=your_google_gemini_api_key
SMTP_EMAIL=your_outlook_email
SMTP_PASSWORD=your_outlook_app_password
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install LaTeX (for PDF compilation)

**Windows:**
```bash
choco install miktex
```

**macOS:**
```bash
brew install --cask mactex-no-gui
```

**Linux:**
```bash
apt-get install texlive-latex-base texlive-fonts-recommended texlive-latex-extra
```

## Usage

### Full Workflow

```bash
# 1. Scrape jobs from public boards
python -m app.main scrape

# 2. Build RAG index (embeds jobs + resume)
python -m app.main index

# 3. Generate tailored resumes and email drafts
python -m app.main generate

# 4. Review and approve emails interactively
python -m app.main review

# 5. Send approved emails (with per-email confirmation)
python -m app.main send
```

### Individual Commands

```bash
# Check system status
python -m app.main status

# Scrape specific boards
python -m app.main scrape --greenhouse figma stripe
python -m app.main scrape --lever netflix spotify

# Force regeneration (ignores cache)
python -m app.main generate --force

# List pending drafts without interactive review
python -m app.main review --list

# Approve/reject specific draft
python -m app.main review --approve <draft_id>
python -m app.main review --reject <draft_id> --reason "Not relevant"

# Send specific email
python -m app.main send --id <draft_id>
```

## Project Structure

```
job-agent/
├── app/                    # Python application code
│   ├── config.py           # Configuration & environment loading
│   ├── scraper.py          # Job scraping from public boards
│   ├── rag.py              # LangChain RAG with FAISS
│   ├── resume_builder.py   # LaTeX resume tailoring
│   ├── email_generator.py  # Cold email draft generation
│   ├── approval.py         # Approval gate system
│   ├── mailer.py           # SMTP email sender
│   └── main.py             # CLI orchestrator
├── resume/
│   └── base_resume.tex     # Your base resume template
├── Dockerfile              # Docker configuration
├── requirements.txt        # Python dependencies
├── cronjob                 # Cron schedule configuration
└── .env.example            # Environment template
```

### Generated Directories (gitignored)

```
├── data/                   # Scraped jobs, contacts, approvals (JSON/CSV)
├── cache/                  # Embeddings, resumes, emails cache
├── rag_index/              # FAISS vector stores
└── resume/compiled/        # Generated PDF resumes
```

## Docker Deployment

```bash
# Build image
docker build -t job-agent .

# Run with cron (scraping only, no sending)
docker run -d --name job-agent job-agent

# Run one-off commands
docker run --rm job-agent python -m app.main status

# View cron logs
docker exec job-agent cat /var/log/cron.log
```

## Safety & Compliance

| Feature | Guarantee |
|---------|-----------|
| **No LinkedIn scraping** | Only public job boards and company pages |
| **No email guessing** | Only extracts publicly visible emails |
| **No auto-sending** | Emails require explicit APPROVED status |
| **CRON_MODE** | When enabled, blocks LLM calls and email sending |
| **LLM limits** | Configurable MAX_LLM_CALLS_PER_RUN (default: 25) |
| **Per-email confirmation** | Even approved emails require send confirmation |

## Cost Optimization

- **Hash-based embedding cache**: Never re-embeds unchanged content
- **Lazy generation**: Skips if resume/email already exists for job
- **Incremental indexing**: Only indexes new documents
- **Configurable limits**: Set MAX_LLM_CALLS_PER_RUN in .env

## Troubleshooting

### "No module found" errors
```bash
pip install langchain-core langchain-google-genai langchain-community faiss-cpu
```

### LaTeX compilation fails
- Ensure `pdflatex` is in your PATH
- Check for missing LaTeX packages in the `.log` file

### SMTP authentication error
- Use an App Password from Outlook security settings
- Ensure 2FA is enabled on your Microsoft account

### No emails discovered
- Many companies don't list public emails
- Try adding more Greenhouse/Lever boards to scrape

## License

MIT License - See LICENSE file for details.

---

**Author**: Lakshay Handa  
**Email**: connect.lakshay@outlook.com
