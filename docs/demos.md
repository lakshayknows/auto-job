# Demos and Examples

This document provides CLI examples, sample outputs, and typical workflow demonstrations.

## CLI Command Reference

### Status Check

```bash
$ python -m app.main status

==================================================
AutoJob Agent Status
==================================================
  CRON_MODE: Inactive
  Jobs Discovered: 15
  Pending Approvals: 2
  Emails Sent: 3
  Archived: 10
==================================================
```

### Job Discovery

```bash
$ python -m app.main discover

2024-01-15 10:30:00 | INFO     | scraper | Starting fresher/intern AI job discovery from legal sources
2024-01-15 10:30:02 | INFO     | scraper | Discovered 45 jobs total, 15 with emails (filtered)
2024-01-15 10:30:02 | INFO     | scraper | Saved 15 jobs (with emails) to data/jobs.json

Discovered 15 jobs
  1. [] Acme Corp - AI Engineer Intern
  2. [] TechStart - Junior ML Engineer
  3. [] DataFlow - Backend Engineer (AI)
  ...
```

### List Jobs

```bash
$ python -m app.main list

Discovered Jobs (15):
----------------------------------------------------------------------
ID         Company              Role                      Email
----------------------------------------------------------------------
a1b2c3d4   Acme Corp            AI Engineer Intern
b5c6d7e8   TechStart            Junior ML Engineer
c9d0e1f2   DataFlow             Backend Engineer (AI)
...

... and 5 more (use --limit to see more)
```

### Process a Job

```bash
$ python -m app.main process a1b2c3d4

Processing: Acme Corp - AI Engineer Intern
Contact: careers@acmecorp.com
--------------------------------------------------
  [scraper] status=N/A, errors=0
  [legal_guard] status=N/A, errors=0
  [source_guard] status=N/A, errors=0
  [cron_check] status=N/A, errors=0
  [rag] status=N/A, errors=0
  [resume] status=N/A, errors=0
  [email] status=N/A, errors=0
--------------------------------------------------

  Waiting for approval. Use 'approve' or 'reject' command.
```

### View Pending Approvals

```bash
$ python -m app.main pending

Pending Approvals (2):
--------------------------------------------------
  a1b2c3d4... | Acme Corp - AI Engineer Intern
  b5c6d7e8... | TechStart - Junior ML Engineer
```

### Approve an Application

```bash
$ python -m app.main approve a1b2c3d4 --notes "Good fit" --resume

 Approved: a1b2c3d4

Processing: Acme Corp - AI Engineer Intern
Contact: careers@acmecorp.com
--------------------------------------------------
  [send_guard] status=N/A, errors=0
  [sender] status=N/A, errors=0
  [archive] status=N/A, errors=0
--------------------------------------------------

 Email sent successfully!
```

### Reject an Application

```bash
$ python -m app.main reject b5c6d7e8 --reason "Not currently hiring"

 Rejected: b5c6d7e8
```

## Example Workflow

### Complete Application Flow

1. **Discover jobs**

```bash
python -m app.main discover
```

2. **Review discovered jobs**

```bash
python -m app.main list --limit 50
```

3. **Process a specific job**

```bash
python -m app.main process a1b2c3d4
```

4. **Review generated artifacts**

   - Resume: `resume/compiled/resume_a1b2c3d4.pdf`
   - Email draft: `data/email_draft_a1b2c3d4.json`

5. **Approve or reject**

```bash
# If satisfied with resume and email
python -m app.main approve a1b2c3d4 --resume

# If not satisfied
python -m app.main reject a1b2c3d4 --reason "Resume needs manual editing"
```

6. **Check final status**

```bash
python -m app.main status
```

## Sample Email Draft

**File**: `data/email_draft_a1b2c3d4.json`

```json
{
  "job_id": "a1b2c3d4e5f6",
  "subject": "Application for AI Engineer Intern at Acme Corp",
  "body": "I am writing to express my interest in the AI Engineer Intern position at Acme Corp.\n\nAs a recent engineering graduate with hands-on experience in deep learning and LLM fine-tuning, I believe I can contribute meaningfully to your team. During my internship at Spartificial, I built deep learning models for astronomical image analysis, processing over 80,000 images and achieving PSNR scores up to 32.7 dB.\n\nI am particularly drawn to Acme Corp's focus on applying AI to real-world problems. Your recent work on automated document processing aligns closely with my interests in practical AI applications.\n\nI would welcome the opportunity to discuss how my skills could benefit your team. I have attached my resume for your consideration.\n\nThank you for your time.",
  "word_count": 128
}
```

## Sample Resume Output

**File**: `resume/compiled/resume_a1b2c3d4.tex`

The generated LaTeX file is a tailored version of your base resume, with:

- Bullet points reordered to emphasize relevant experience
- Skills section adjusted to highlight matching technologies
- Projects reworded to align with job requirements
- No fabricated experience or skills

## Sample Log Output

**File**: `data/logs/autojob.log`

```
2024-01-15 10:30:00 | INFO     | autojob | Starting job discovery
2024-01-15 10:30:02 | INFO     | scraper | Fetched 25 jobs from RemoteOK
2024-01-15 10:30:03 | INFO     | scraper | Fetched 20 jobs from HackerNews
2024-01-15 10:30:05 | INFO     | scraper | Email enrichment complete: 15 emails found
2024-01-15 10:30:05 | INFO     | scraper | Saved 15 jobs to data/jobs.json

2024-01-15 10:35:00 | INFO     | main | Processing job: a1b2c3d4
2024-01-15 10:35:00 | INFO     | guards | Legal check passed for job a1b2c3d4
2024-01-15 10:35:00 | INFO     | guards | Email source validated: careers@acmecorp.com
2024-01-15 10:35:01 | INFO     | rag | Retrieved RAG context: 8 job skills, 12 resume skills
2024-01-15 10:35:05 | INFO     | resume | Saved tailored resume: resume/compiled/resume_a1b2c3d4.tex
2024-01-15 10:35:08 | INFO     | resume | Compiled PDF: resume/compiled/resume_a1b2c3d4.pdf
2024-01-15 10:35:10 | INFO     | email | Drafted email for a1b2c3d4: 128 words

2024-01-15 10:35:10 | INFO     | approval |
========================================
APPROVAL REQUIRED
========================================
Job ID: a1b2c3d4e5f6
Company: Acme Corp
Role: AI Engineer Intern
Contact: careers@acmecorp.com

Email Draft:
[email content here]
========================================

2024-01-15 10:40:00 | INFO     | approval | Saved approval: a1b2c3d4 -> APPROVED
2024-01-15 10:40:00 | INFO     | guards | Send guard passed for job a1b2c3d4
2024-01-15 10:40:01 | INFO     | sender | Connecting to SMTP: smtp.office365.com:587
2024-01-15 10:40:03 | INFO     | sender | Email sent successfully: a1b2c3d4 -> careers@acmecorp.com
2024-01-15 10:40:03 | INFO     | sender | Archived job a1b2c3d4: SENT
```

## Activity Log

**File**: `data/activity.csv`

```csv
Timestamp,Event,Job ID,Company,Details
2024-01-15 10:30:05,DISCOVERED,a1b2c3d4,Acme Corp,AI Engineer Intern (careers@acmecorp.com)
2024-01-15 10:30:05,DISCOVERED,b5c6d7e8,TechStart,Junior ML Engineer (jobs@techstart.io)
2024-01-15 10:40:00,APPROVED,a1b2c3d4,Unknown,Notes: Good fit
2024-01-15 10:40:03,SENT,a1b2c3d4,Acme Corp,To: careers@acmecorp.com
2024-01-15 10:45:00,REJECTED,b5c6d7e8,Unknown,Reason: Not currently hiring
```

## CRON_MODE Example

When `CRON_MODE=true`:

```bash
$ CRON_MODE=true python -m app.main process a1b2c3d4

Processing: Acme Corp - AI Engineer Intern
Contact: careers@acmecorp.com
--------------------------------------------------
  [scraper] status=N/A, errors=0
  [legal_guard] status=N/A, errors=0
  [source_guard] status=N/A, errors=0
  [cron_check] status=N/A, errors=1
  [archive] status=N/A, errors=0
--------------------------------------------------

 Errors: ['CRON_MODE active - LLM blocked']
```

The job is archived without LLM processing.

## Error Examples

### Missing Email

```bash
$ python -m app.main process c9d0e1f2

Processing: DataFlow - Backend Engineer (AI)
Contact: N/A
--------------------------------------------------
  [send_guard] status=N/A, errors=1
--------------------------------------------------

 Errors: ['No contact email']
```

### Blocked Domain

```bash
# If a job somehow references LinkedIn
  [legal_guard] status=N/A, errors=1
--------------------------------------------------

 Errors: ['Blocked domain: linkedin.com']
```

### Cost Limit

```bash
# After many LLM calls
  [cron_check] status=N/A, errors=1
--------------------------------------------------

 Errors: ['Cost limit: 30 LLM calls']
```
