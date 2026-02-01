# Job Automation System

A production-grade, legal, and approval-gated job automation system that scrapes job listings, tailors resumes using RAG, drafts personalized cold emails, and sends only after explicit human approval.

## Features

- **Legal Scraping**: Only scrapes public job boards (RemoteOK, Greenhouse, Lever ATS)
- **Public Email Discovery**: Extracts only publicly visible hiring emails
- **RAG-Powered Personalization**: Uses LangChain + Google Gemini for context-aware generation
- **LaTeX Resumes**: Generates tailored `.tex` files compiled to PDF
- **Approval Gate**: Tri-state approval system (PENDING/APPROVED/REJECTED)
- **Cost Optimization**: Hash-based caching, lazy loading, LLM call limits
- **Docker + Cron**: Automated weekly scraping (never auto-sends emails)

## Project Structure

```
job-agent/
├── prompts/           # RALPH-style prompts
├── data/              # JSON/CSV data storage
├── cache/             # Embeddings, resumes, emails cache
├── resume/            # Base resume + compiled PDFs
├── app/               # Python application code
├── rag_index/         # FAISS vector stores
├── Dockerfile
├── requirements.txt
├── cronjob
└── .env
```

## Setup

### 1. Environment Configuration

Edit `.env` with your credentials:

```bash
GOOGLE_API_KEY=your_google_api_key
OPENROUTER_API_KEY=your_openrouter_key
SMTP_PASSWORD=your_outlook_app_password
```

### 2. Install Dependencies

```bash
cd job-agent
pip install -r requirements.txt
```

### 3. Install LaTeX (for PDF compilation)

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
apt-get install texlive-latex-base texlive-fonts-recommended
```

## Usage

### Scrape Jobs

```bash
# Scrape from RemoteOK
python -m app.main scrape

# Scrape from Greenhouse boards
python -m app.main scrape --greenhouse figma stripe

# Scrape from Lever boards
python -m app.main scrape --lever netflix spotify
```

### Build RAG Index

```bash
python -m app.main index
```

### Generate Resumes & Emails

```bash
# Generate (uses lazy loading - skips cached)
python -m app.main generate

# Force regeneration
python -m app.main generate --force
```

### Review & Approve Emails

```bash
# Interactive review
python -m app.main review

# List pending drafts
python -m app.main review --list

# Approve specific draft
python -m app.main review --approve <draft_id>

# Reject with reason
python -m app.main review --reject <draft_id> --reason "Not a good fit"
```

### Send Approved Emails

```bash
# Send all approved (with per-email confirmation)
python -m app.main send

# Send specific email
python -m app.main send --id <draft_id>
```

### Check Status

```bash
python -m app.main status
```

## Docker Deployment

### Build Image

```bash
docker build -t job-agent .
```

### Run Container

```bash
# Run with cron (scraper only, no sending)
docker run -d --name job-agent job-agent

# Run one-off command
docker run --rm job-agent python -m app.main status
```

### View Logs

```bash
docker logs job-agent
docker exec job-agent cat /var/log/cron.log
```

## Data Schemas

### jobs.json
```json
{
  "id": "uuid",
  "company": "Company Name",
  "role": "Role Title",
  "description": "Full job description",
  "url": "https://...",
  "company_website": "https://...",
  "scraped_at": "ISO8601",
  "source": "remoteok|greenhouse|lever"
}
```

### contacts.json
```json
{
  "job_id": "uuid",
  "company": "Company Name",
  "email": "careers@company.com",
  "source": "https://company.com/careers",
  "discovered_at": "ISO8601"
}
```

### approvals.json
```json
{
  "id": "uuid",
  "job_id": "uuid",
  "company": "Company Name",
  "role": "Role Title",
  "to_email": "careers@company.com",
  "subject": "Application for Role",
  "body": "Email body",
  "resume_path": "resume/compiled/...",
  "approval_status": "PENDING|APPROVED|REJECTED",
  "sent": false,
  "created_at": "ISO8601"
}
```

## Safety Features

1. **CRON_MODE**: When enabled, blocks all LLM calls and email sending
2. **MAX_LLM_CALLS_PER_RUN**: Hard limit on API usage (default: 25)
3. **Tri-state Approval**: Emails must be explicitly APPROVED before sending
4. **Per-email Confirmation**: Even approved emails require confirmation to send
5. **No LinkedIn Scraping**: Only scrapes public job boards and company pages
6. **No Email Guessing**: Only uses publicly visible hiring emails

## Cost Optimization

- **Hash-based Embedding Cache**: Never re-embeds unchanged content
- **Lazy Resume Generation**: Skips if resume already exists for job
- **Lazy Email Drafting**: Generates once per job
- **Incremental Indexing**: Only indexes new documents

## Troubleshooting

### LaTeX Compilation Fails
- Ensure `pdflatex` is in your PATH
- Check for missing LaTeX packages
- Review the `.log` file in `resume/compiled/`

### SMTP Authentication Error
- Use an App Password, not your regular password
- Enable "Less secure app access" in Outlook (if applicable)

### No Emails Discovered
- Company websites may not list public emails
- Try adding more job boards to scrape

## License

MIT License - See LICENSE file for details.
