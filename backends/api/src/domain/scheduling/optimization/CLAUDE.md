# CP-SAT Constraint Inputs and Work Cell Semantics

Location: app/domain/scheduling/optimization

Purpose: Document how resource allocation, work cells, calendars, skills, and business rules feed the CP-SAT model so inputs can be validated, snapshotted, and reproduced.

Key concepts
- Work cell: a logical grouping of machines and buffers with shared WIP limits
- Machine: capacity 1 by default; calendars and maintenance windows reduce availability
- Operator: skill vectors and shift calendars; proficiency affects assignment score
- Task: precedence order, setup/teardown, eligible machines/operators
- Routing: alternative machines per operation with potential changeover cost

Inputs to capture per run
- Planning horizon and granularity
- Task set: ids, durations, precedence, due dates, priorities
- Resources: machines (by cell), operators, skills matrix, calendars
- Business constraints: work hours, holidays, WIP limits, zone routing
- Objective weights and solver parameters

Persistence guidance
- Compute inputs_hash over a normalized JSON bundle
- Store JSON bundle in optimization_runs.inputs_snapshot for replay

Validation
- Use SchedulingProblem.validate_problem() and ConstraintValidator to produce violations list; persist violations to optimization_solutions.constraint_violations or events table at START

Performance notes
- Tighten time_granularity_minutes to balance model size vs fidelity
- Use relative_gap_limit with time cap for graceful trade-offs
- Prefer partial feasible solutions over timeouts; mark status=feasible and record gap

