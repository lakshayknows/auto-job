# Security Policy

## Supported Versions

The following versions of AutoJob are currently supported with security updates.

| Version | Supported |
| ------ | --------- |
| main / latest | ✅ |
| pre-release / experimental branches | ❌ |
| archived releases | ❌ |

Only the latest version on the `main` branch receives security patches. Users are strongly encouraged to stay up to date.

---

## Security Design Principles

AutoJob is designed with **safety, compliance, and human oversight** as first-class concerns.

Key security properties:

- **No autonomous outbound actions**
  - Emails are never sent without explicit human approval.
- **CRON_MODE hard isolation**
  - Scheduled runs are strictly read-only.
  - LLM calls, resume generation, email drafting, and sending are physically blocked.
- **Human-in-the-loop enforcement**
  - All outbound communication requires manual approval.
- **No credential persistence**
  - API keys are loaded only from environment variables.
  - No secrets are committed to the repository.
- **Prompt safety**
  - Prompts are templated and parameterized.
  - No raw string interpolation in LLM inputs.
- **Cost and abuse guards**
  - LLM usage is rate-limited and explicitly tracked.
- **Legal scraping only**
  - Only public job listings and publicly listed company/HR emails are processed.
  - No scraping of private profiles or authenticated platforms.

---

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

### How to Report

- **Email:** `connect.lakshay@outlook.com`
- **Subject:** `Security Vulnerability Report – AutoJob`

Please include:
- A clear description of the issue
- Steps to reproduce (if applicable)
- Potential impact
- Any relevant logs or screenshots

### What to Expect

- **Acknowledgement:** within 72 hours
- **Initial assessment:** within 5 business days
- **Fix or mitigation:** as quickly as possible depending on severity

You will be notified whether the report is accepted, declined, or requires additional information.

---

## Scope of Vulnerabilities

### In Scope
- Unauthorized outbound actions (emails, data exfiltration)
- Bypassing approval or CRON_MODE safeguards
- Credential leakage or improper secret handling
- Prompt injection leading to unintended behavior
- Unsafe automation paths
- Abuse of CLI or graph execution paths

### Out of Scope
- Issues in third-party services (LLMs, email providers)
- Social engineering attacks
- Denial-of-service via excessive legitimate usage
- Misuse outside documented behavior

---

## Responsible Disclosure

Please do **not** publicly disclose vulnerabilities until they have been reviewed and addressed. Responsible disclosure helps keep users and contributors safe.

Thank you for helping improve the security of AutoJob.
