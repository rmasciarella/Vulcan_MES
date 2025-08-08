# Zen Code Review Framework

This directory contains the Zen Code Review framework used to drive consistent, DDD-aligned, and enforcement-ready reviews across the monorepo.

Contents
- acceptance-criteria.md — The definitive checklist for acceptance on main
- severity-levels.md — Definitions and SLAs for finding severities
- templates/review-log.md — Markdown template to record findings
- templates/review-log.schema.json — JSON Schema enforcing structure of findings logs
- templates/review-log.yaml.example — Example YAML log compatible with the schema
- logs/ — Place to store filled-out review logs per review cycle or PR

Usage
1) Before review: skim acceptance-criteria.md and severity-levels.md
2) During review: capture findings using templates/review-log.md (or JSON/YAML matching review-log.schema.json)
3) After review: store the filled log in logs/<date-or-pr>-<short-title>.md and link it in your PR/issue

Tips
- Map each finding to one or more acceptance criteria IDs
- Use the smallest severity that will still drive the right behavior
- Prefer actionable remediation steps with owners and dates
- For DDD alignment, tag affected bounded contexts (e.g., Scheduling, Work Orders) in the "tags" field

