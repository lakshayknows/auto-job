# How It Works

This document provides a step-by-step walkthrough of the AutoJob Agent system.

## Overview

The system automates job applications through a controlled pipeline:

1. Discover jobs from legal public sources
2. Extract company contact emails
3. Retrieve relevant context using RAG
4. Tailor resume for the specific role
5. Draft a cold email
6. Wait for human approval
7. Send the email if approved

Each step has built-in safety checks.

## Step 1: Job Discovery

**Node**: `scraper`
**File**: `app/nodes/scraper.py`

The scraper fetches jobs from:

- **RemoteOK**: Public JSON API at `remoteok.com/api`
- **Hacker News**: "Who is Hiring" posts via Firebase API

### What Happens

1. Jobs are fetched from each source
2. Only jobs matching target keywords (AI, ML, intern, fresher, etc.) are kept
3. For each job, the scraper attempts to find a public company email
4. Email discovery checks only allowed paths (`/careers`, `/jobs`, `/contact`, etc.)
5. Only emails with allowed prefixes (`careers@`, `jobs@`, `hr@`, etc.) are kept
6. Jobs are saved to `data/jobs.json`

### What Is Blocked

- LinkedIn scraping (domain blocked)
- Facebook, Twitter/X, Instagram (domains blocked)
- Personal profile pages
- PDFs or gated content

## Step 2: Legal Guard

**Node**: `legal_guard`
**File**: `app/nodes/guards.py`

### What Happens

1. Checks if job URL, company URL, or email source contains blocked domains
2. Checks if job source is recognized (RemoteOK, HackerNews, etc.)
3. If checks fail, job is marked for skip and goes to archive

### Why This Exists

Some jobs may be discovered through allowed sources but link to blocked sites. This guard catches those cases.

## Step 3: Source Guard

**Node**: `source_guard`
**File**: `app/nodes/guards.py`

### What Happens

1. Validates that the contact email has an appropriate prefix
2. Personal emails are only allowed if `contact_type` is explicitly `HR`
3. Invalid emails are cleared from state

### Why This Exists

Prevents sending cold emails to personal addresses that were not explicitly listed as hiring contacts.

## Step 4: CRON Mode Check

**Node**: `cron_check`
**File**: `app/graph.py`

### What Happens

1. If `CRON_MODE=true` in environment, sets `should_skip=True`
2. Also runs cost guard to check LLM call limits

### Why This Exists

CRON_MODE allows running the scraper on a schedule without accidentally triggering LLM calls or sending emails. Only discovery is allowed.

## Step 5: RAG Context Retrieval

**Node**: `rag`
**File**: `app/nodes/rag.py`

### What Happens

1. Loads base resume from `resume/base_resume.tex`
2. Splits job description and resume into chunks
3. Creates vector indexes using ChromaDB (if available)
4. Retrieves relevant chunks for:
   - Job skills and responsibilities
   - Matching resume experience and projects
5. Falls back to keyword extraction if ChromaDB is unavailable

### What Is Blocked

- If CRON_MODE is active, this node is skipped
- If RAG context already exists, retrieval is skipped (cached)

## Step 6: Resume Tailoring

**Node**: `resume`
**File**: `app/nodes/resume.py`

### What Happens

1. Loads base resume LaTeX template
2. Calls Gemini LLM to tailor resume for the job
3. Cleans response (removes markdown code blocks if present)
4. Validates output starts with `\documentclass`
5. Saves tailored LaTeX to `resume/compiled/resume_{job_id}.tex`
6. Compiles to PDF using `pdflatex`
7. Results are cached per job_id

### Why LaTeX Only

LaTeX ensures deterministic, professional formatting. No HTML or image resumes are generated.

### What Is Blocked

- If CRON_MODE is active, this node is skipped
- If cached resume exists, LLM is not called

## Step 7: Email Drafting

**Node**: `email`
**File**: `app/nodes/email.py`

### What Happens

1. Calls Gemini LLM to draft cold email
2. Enforces 200-word limit (truncates if exceeded)
3. Generates subject line
4. Saves draft to `data/email_draft_{job_id}.json`
5. Results are cached per job_id

### What Is Blocked

- If CRON_MODE is active, this node is skipped
- If cached draft exists, LLM is not called

## Step 8: Approval Gate

**Node**: `approval`
**File**: `app/nodes/approval.py`

### What Happens

1. Checks if approval already exists in `data/approvals.json`
2. If not, logs the pending approval and pauses execution
3. Graph enters `interrupt_before` state
4. User must run `approve` or `reject` CLI command
5. Decision is saved with timestamp

### Why This Is Critical

This is the human-in-the-loop guarantee. No email can proceed without explicit human action.

### Routing After Approval

| Status | Next Step |
|--------|-----------|
| APPROVED | Send Guard |
| REJECTED | Archive |
| PENDING | Wait (graph paused) |

## Step 9: Send Guard

**Node**: `send_guard`
**File**: `app/nodes/guards.py`

### What Happens

Performs final safety checks:

1. `approval_status == APPROVED`
2. `contact_email` is not null
3. Resume PDF exists on disk
4. Email not already sent
5. `CRON_MODE == false`

If any check fails, sending is blocked and errors are logged.

### Why This Exists

Defense in depth. Even if approval is granted, all preconditions must be satisfied.

## Step 10: Email Sending

**Node**: `sender`
**File**: `app/nodes/sender.py`

### What Happens

1. Creates MIME multipart message
2. Attaches email body as plain text
3. Attaches resume PDF if available
4. Connects to SMTP server (Gmail by default)
5. Sends email
6. Logs sent email to `data/sent_emails.json`

### What Is Blocked

- If CRON_MODE is active, sending is blocked
- If approval status is not APPROVED, sending is blocked
- If email was already sent, sending is blocked

## Step 11: Archiving

**Node**: `archive`
**File**: `app/nodes/sender.py`

### What Happens

1. Saves final job state to `data/archive.json`
2. Records approval status, sent flag, and any errors
3. Adds timestamp

### Why This Exists

Creates an audit trail of all processed jobs.

## Summary Table

| Step | Node | LLM | Network | Blocked By CRON |
|------|------|-----|---------|-----------------|
| 1 | scraper | No | Yes | No |
| 2 | legal_guard | No | No | No |
| 3 | source_guard | No | No | No |
| 4 | cron_check | No | No | No (is the blocker) |
| 5 | rag | Yes* | Yes* | Yes |
| 6 | resume | Yes | No | Yes |
| 7 | email | Yes | No | Yes |
| 8 | approval | No | No | No |
| 9 | send_guard | No | No | Yes (blocks send) |
| 10 | sender | No | Yes | Yes |
| 11 | archive | No | No | No |

*RAG uses embeddings API and ChromaDB
