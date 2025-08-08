# Severity Levels

Use these levels to classify findings consistently. When in doubt, choose the lowest level that effectively drives remediation.

Critical
- Definition: Breaks core acceptance criteria or causes security/data loss risk; blocks release.
- Examples: Services cannot boot with `docker-compose up`; tests red on main; RCE/credential exposure.
- SLA: Immediate fix before merge or hotfix.

High
- Definition: Materially degrades reliability, quality, or developer experience; likely to fail acceptance in CI.
- Examples: Flaky E2E/tests without quarantine; coverage <95% for changed area; broken type-checks.
- SLA: Address in current iteration before release.

Medium
- Definition: Non-blocking but meaningful tech debt or maintainability concern; could cause incidents if left.
- Examples: Missing DDD boundaries in new code; untyped public APIs; slow tests.
- SLA: Scheduled within 1–2 sprints with owner.

Low
- Definition: Cosmetic or minor improvement with low risk/impact.
- Examples: Naming/style nits; small docs gaps.
- SLA: Opportunistic; batch with nearby changes.

