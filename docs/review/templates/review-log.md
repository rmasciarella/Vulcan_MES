---
title: "Review Log Template"
description: "Use this template to record review findings. One file per review cycle or PR is recommended."
---

# Review Metadata
- Review ID: REW-<YYYYMMDD>-<slug>
- Date: <YYYY-MM-DD>
- Reviewer(s): <names>
- Scope: <services / apps / domains>
- Related PR/Issue: <links>

# Findings

Use one section per finding. Severity must be one of: Critical | High | Medium | Low

## Finding <incremental-number>
- Title: <short, action-oriented>
- Area: <service/app/module/domain>
- File(s): <paths if applicable>
- Severity: <Critical|High|Medium|Low>
- Acceptance Criteria: [AC-1|AC-2|AC-3|AC-4|AC-5|AC-6]
- Status: <Open|In Progress|Mitigated|Accepted|Closed>
- Owner: <person/team>
- Due Date: <YYYY-MM-DD>
- Evidence:
  - <log, screenshot link, stacktrace, CI run link>
- Impact: <who/what is affected, user impact, risk>
- Recommendation: <clear remediation steps>
- Notes: <context, tradeoffs>

Repeat the "Finding" section for each item.

# Summary
- Total Findings: <n>
- By Severity: Critical <n> | High <n> | Medium <n> | Low <n>
- Accepted Risk Items: <n> (list IDs)
- Follow-ups Created: <links to tickets>

