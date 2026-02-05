# Architecture

This document describes the technical architecture of the AutoJob Agent system.

## Why LangGraph

LangGraph was chosen for this project because:

1. **Explicit State Management**: Job application workflows require clear state transitions. LangGraph's typed state model ensures every field is tracked and serializable.

2. **Human-in-the-Loop Native**: LangGraph's interrupt mechanism allows the graph to pause at the approval node, wait for human input, and resume without losing state.

3. **Conditional Routing**: Guards (legal, cost, send) require conditional edges. LangGraph's `add_conditional_edges` makes this explicit and testable.

4. **Checkpointing**: State persistence via `MemorySaver` enables resuming interrupted workflows.

5. **No Hidden Magic**: Unlike pure agentic loops, LangGraph forces explicit node definitions and edge routing, making the system auditable.

## High-Level System Flow

```
                    START
                      |
                      v
               +-----------+
               |  Scraper  |
               +-----------+
                      |
                      v
              +-------------+
              | Legal Guard |
              +-------------+
                      |
            +---------+---------+
            |                   |
          PASS                FAIL
            |                   |
            v                   v
       +------------+      +--------+
       |Source Guard|      |Archive |
       +------------+      +--------+
            |                   |
            v                   |
       +------------+           |
       | CRON Check |           |
       +------------+           |
            |                   |
      +-----+-----+             |
      |           |             |
   CONTINUE     SKIP            |
      |           |             |
      v           v             |
   +-----+    +--------+        |
   | RAG |    |Archive |        |
   +-----+    +--------+        |
      |           |             |
      v           |             |
   +--------+     |             |
   | Resume |     |             |
   +--------+     |             |
      |           |             |
      v           |             |
   +-------+      |             |
   | Email |      |             |
   +-------+      |             |
      |           |             |
      v           |             |
   +----------+   |             |
   | Approval |<--+-------------+
   +----------+
        |
   +----+----+--------+
   |         |        |
APPROVED  REJECTED  PENDING
   |         |        |
   v         v        v
+----------+ +------+ (WAIT)
|Send Guard| |Archive|
+----------+ +------+
   |           |
   +-----+-----+
   |     |
  PASS  FAIL
   |     |
   v     v
+------+ +------+
|Sender| |Archive|
+------+ +------+
   |       |
   v       |
+------+   |
|Archive|<-+
+------+
   |
   v
  END
```

## Node Responsibilities

| Node | File | Purpose |
|------|------|---------|
| `scraper` | `nodes/scraper.py` | Discover jobs from legal public sources |
| `legal_guard` | `nodes/guards.py` | Block jobs from disallowed domains |
| `source_guard` | `nodes/guards.py` | Validate email prefix is appropriate |
| `cron_check` | `graph.py` | Block LLM operations in CRON_MODE |
| `rag` | `nodes/rag.py` | Retrieve relevant context for tailoring |
| `resume` | `nodes/resume.py` | Generate tailored LaTeX resume |
| `email` | `nodes/email.py` | Draft cold email (max 200 words) |
| `approval` | `nodes/approval.py` | Pause for human approval |
| `send_guard` | `nodes/guards.py` | Final safety check before sending |
| `sender` | `nodes/sender.py` | Send email via SMTP |
| `archive` | `nodes/sender.py` | Archive completed job application |

## State Model

The system uses a `TypedDict` for state, ensuring serializability. Key fields:

```python
class JobState(TypedDict, total=False):
    # Identification
    job_id: str
    job_data: JobData

    # Contact
    contact_email: Optional[str]
    contact_type: Literal["COMPANY", "HR", "UNKNOWN"]

    # Artifacts
    resume_tex_path: Optional[str]
    resume_pdf_path: Optional[str]
    email_draft: Optional[str]
    email_subject: Optional[str]

    # RAG
    rag_context: Optional[RAGContext]

    # Approval
    approval_status: Literal["PENDING", "APPROVED", "REJECTED"]
    sent: bool

    # Tracking
    errors: list[str]
    llm_calls: int
    total_tokens: int

    # Guards
    legal_check_passed: bool
    send_guard_passed: bool
    should_skip: bool
    skip_reason: Optional[str]
```

All fields are JSON-serializable primitives or nested dicts/lists.

## Approval Interrupt Design

The approval mechanism uses LangGraph's `interrupt_before` feature:

```python
app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["approval"],
)
```

When the graph reaches the `approval` node:

1. Execution pauses
2. State is persisted via checkpointer
3. CLI shows pending approval
4. User runs `approve` or `reject` command
5. Approval status is saved to `data/approvals.json`
6. Graph is resumed with `app.stream(state, config)`
7. Routing function reads approval status and proceeds accordingly

This design ensures:

- No email can be sent without explicit human action
- State is not lost during interruption
- Approval decisions are logged and auditable

## Key Design Decisions

1. **No LinkedIn Scraping**: Legal compliance is non-negotiable. Blocked domains are hardcoded.

2. **LaTeX Only**: Resume output is always LaTeX. No PDF generation without `pdflatex`.

3. **Word Limit Enforcement**: Email drafts are truncated to 200 words in code, not just in prompts.

4. **Caching Per Job**: Resume and email drafts are cached per `job_id[:8]` to avoid redundant LLM calls.

5. **CRON_MODE Blocks Everything**: When active, LLM nodes and sender are blocked at multiple levels.
