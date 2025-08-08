# /log - Development Workflow Manager

## Description

Intelligent development workflow manager that tracks progress, suggests next tasks, records lessons learned, and maintains lean context across Claude sessions.

## Usage

- `/log` - Show current status and suggest next priority tasks
- `/log next` - Focus on next tasks with agent recommendations
- `/log done [description]` - Mark task complete and record lessons
- `/log status` - Comprehensive project overview
- `/log blockers` - Show current blockers and risks
- `/log prune` - Clean up outdated context from CLAUDE.md
- `/log archive [phase]` - Archive completed phase information

## Implementation

```javascript
// The /log command intelligently manages development workflow
// It reads DEVELOPMENT_PLAN.md and CLAUDE.md to provide context-aware assistance

const fs = require('fs').promises
const path = require('path')

async function executeLogCommand(args) {
  const command = args[0] || 'default'
  const devPlanPath = 'docs/DEVELOPMENT_PLAN.md'
  const claudeMdPath = 'docs/worklog/CLAUDE.md'

  // Read current project state
  const devPlan = await fs.readFile(devPlanPath, 'utf-8')
  const claudeMd = await fs.readFile(claudeMdPath, 'utf-8')

  switch (command) {
    case 'next':
      return await getNextTasks(devPlan, claudeMd)
    case 'done':
      return await markTaskComplete(args.slice(1).join(' '), claudeMd)
    case 'status':
      return await getProjectStatus(devPlan, claudeMd)
    case 'blockers':
      return await getBlockers(devPlan, claudeMd)
    case 'prune':
      return await pruneContext(claudeMd)
    case 'archive':
      return await archivePhase(args[1], claudeMd)
    default:
      return await getSmartStatus(devPlan, claudeMd)
  }
}

async function getNextTasks(devPlan, claudeMd) {
  // Parse development plan for incomplete tasks
  const phases = parsePhases(devPlan)
  const currentPhase = getCurrentPhase(claudeMd)
  const tasks = []

  // Priority 1: Fix blockers (e.g., 27 failing tests in Tasks domain)
  const blockers = findBlockers(claudeMd)
  if (blockers.length > 0) {
    tasks.push({
      priority: 'CRITICAL',
      task: blockers[0],
      agent: 'debugger or test-automator',
      command: 'Use @debugger or @test-automator agent to fix failing tests',
    })
  }

  // Priority 2: Continue current domain implementation
  const incompleteDomains = findIncompleteDomains(claudeMd)
  if (incompleteDomains.length > 0) {
    tasks.push({
      priority: 'HIGH',
      task: `Implement ${incompleteDomains[0]} domain`,
      agent: 'implementation-specialist',
      command: 'Use @implementation-specialist to build domain entities and repositories',
    })
  }

  // Priority 3: Integration tasks
  const integrationNeeded = findIntegrationTasks(claudeMd)
  if (integrationNeeded.length > 0) {
    tasks.push({
      priority: 'MEDIUM',
      task: integrationNeeded[0],
      agent: 'system-architect',
      command: 'Use @system-architect for cross-domain integration',
    })
  }

  return formatTaskList(tasks)
}

async function markTaskComplete(description, claudeMd) {
  const timestamp = new Date().toISOString().split('T')[0]
  const lesson = promptForLesson(description)

  // Update CLAUDE.md with completion
  const updatedMd = updateTaskStatus(claudeMd, description, 'complete')

  // Add to lessons learned
  const lessonsSection = `\\n## Lessons Learned\\n- ${timestamp}: ${description}\\n  ${lesson}\\n`

  // Prune outdated information
  const prunedMd = intelligentPrune(updatedMd)

  await fs.writeFile('docs/worklog/CLAUDE.md', prunedMd)

  return `✅ Task marked complete and lessons recorded. Context pruned.`
}

async function getProjectStatus(devPlan, claudeMd) {
  const phases = parsePhases(devPlan)
  const status = {
    overall: calculateOverallProgress(phases),
    currentPhase: getCurrentPhase(claudeMd),
    completedDomains: ['Jobs (104 tests)'],
    inProgressDomains: ['Tasks (27 failing tests)'],
    pendingDomains: ['Resources', 'Scheduling', 'Constraints'],
    timeline: {
      elapsed: 'Week 4 of 23',
      remaining: '19 weeks',
      onTrack: false,
      risk: 'HIGH - Tasks domain blocking progress',
    },
  }

  return formatStatusReport(status)
}

async function getBlockers(devPlan, claudeMd) {
  const blockers = []

  // Check for failing tests
  if (claudeMd.includes('27 failing tests')) {
    blockers.push({
      severity: 'CRITICAL',
      domain: 'Tasks',
      issue: '27 failing tests blocking domain completion',
      impact: 'Cannot proceed with Resources domain',
      resolution: 'Fix TaskId.create() and TaskMode integration',
      agent: 'debugger',
      estimatedTime: '2-4 hours',
    })
  }

  // Check for incomplete dependencies
  const dependencies = checkDependencies(devPlan, claudeMd)
  blockers.push(...dependencies)

  return formatBlockerReport(blockers)
}

async function pruneContext(claudeMd) {
  // Identify outdated sections
  const sections = {
    keep: [
      'Current Focus',
      'Next Phase 2 Steps',
      'Implementation Status Summary',
      'Key URLs and Resources',
      'Lessons Learned',
    ],
    archive: [],
    remove: [],
  }

  // Find completed work older than 2 weeks
  const oldCompletedWork = findOldCompletedSections(claudeMd)
  sections.archive.push(...oldCompletedWork)

  // Remove redundant information
  const redundant = findRedundantInfo(claudeMd)
  sections.remove.push(...redundant)

  // Create archive file
  if (sections.archive.length > 0) {
    const archivePath = `docs/worklog/archive/phase2_${Date.now()}.md`
    await createArchive(sections.archive, archivePath)
  }

  // Update CLAUDE.md
  const prunedMd = removeOutdatedSections(claudeMd, sections)
  await fs.writeFile('docs/worklog/CLAUDE.md', prunedMd)

  return `✅ Context pruned. Archived ${sections.archive.length} sections, removed ${sections.remove.length} redundant items.`
}

// Helper functions for intelligent behavior
function suggestAgent(taskType) {
  const agentMap = {
    implement: 'implementation-specialist',
    test: 'test-automator',
    debug: 'debugger',
    integrate: 'system-architect',
    optimize: 'performance-engineer',
    security: 'security-auditor',
    database: 'database-optimizer',
    ui: 'frontend-developer',
    review: 'code-reviewer',
  }

  for (const [key, agent] of Object.entries(agentMap)) {
    if (taskType.toLowerCase().includes(key)) {
      return agent
    }
  }
  return 'general-purpose'
}

function calculateUrgency(task, blockers, timeline) {
  let urgency = 0

  // Blocker urgency
  if (blockers.some((b) => b.impacts.includes(task))) urgency += 10

  // Timeline urgency
  const weeksRemaining = 23 - getCurrentWeek()
  if (weeksRemaining < 10) urgency += 5

  // Dependency urgency
  if (hasDependents(task)) urgency += 3

  return urgency
}

function formatTaskWithAgent(task) {
  const agent = suggestAgent(task.type)
  return `
📋 **Task**: ${task.description}
🤖 **Recommended Agent**: @${agent}
🚀 **Quick Start**: 
\`\`\`
@${agent} ${task.quickCommand || task.description}
\`\`\`
⏱️ **Estimated Time**: ${task.estimate || 'Unknown'}
🔗 **Dependencies**: ${task.dependencies.join(', ') || 'None'}
  `
}

module.exports = { executeLogCommand }
```

## Features

### Intelligent Context Detection

- Analyzes user input to determine intent (checking status vs completing work)
- Automatically identifies current phase and priority based on project state
- Detects blockers and suggests resolution strategies

### Agent Recommendations

Maps task types to appropriate Claude agents:

- **Implementation tasks** → `@implementation-specialist`
- **Testing/debugging** → `@debugger` or `@test-automator`
- **Integration** → `@system-architect`
- **Performance** → `@performance-engineer`
- **Security** → `@security-auditor`
- **Database** → `@database-optimizer`
- **UI/Frontend** → `@frontend-developer`
- **Code review** → `@code-reviewer`

### Progress Tracking

- Monitors completion across 11 phases
- Tracks 8 domain implementations
- Calculates velocity and provides estimates
- Identifies critical path and bottlenecks

### Context Management

- **Auto-pruning**: Removes outdated information after 2 weeks
- **Archiving**: Moves completed phase details to archive files
- **Lessons database**: Preserves learnings in searchable format
- **Smart filtering**: Keeps only relevant context for current work

### Risk Assessment

- Detects blockers (e.g., failing tests, missing dependencies)
- Calculates urgency based on timeline and dependencies
- Provides mitigation strategies
- Alerts to potential delays

## Examples

### Check what to work on next

```
/log next

📋 CRITICAL: Fix Tasks domain - 27 failing tests
🤖 Recommended Agent: @debugger
🚀 Quick Start: @debugger Fix 27 failing tests in Tasks domain, starting with TaskId.create()
⏱️ Estimated: 2-4 hours
🔗 Blocking: Resources domain implementation
```

### Mark task complete with lessons

```
/log done Fixed TaskId.create() method in Tasks domain

✅ Task complete! What lesson did you learn?
> "Always validate ID creation before using in value objects"

✓ Recorded lesson and updated progress
✓ Pruned 3 outdated context sections
→ Next: Complete remaining Task domain tests (21 remaining)
```

### Get project status

```
/log status

📊 Vulcan MES Development Status
================================
Overall Progress: 16% (Week 4 of 23)
Current Phase: Phase 2 - Core Domain Implementation (20%)

✅ Completed:
- Jobs Domain (100% - 104 tests passing)

🔄 In Progress:
- Tasks Domain (30% - 27 failing tests) ⚠️ BLOCKED

📅 Upcoming:
- Resources Domain (0%)
- Scheduling Domain (0%)
- Constraints Domain (0%)

⚠️ Risk Level: HIGH
- Behind schedule by 1 week
- Tasks domain blocking critical path
```

### Show blockers

```
/log blockers

🚨 Current Blockers
==================
1. CRITICAL: Tasks Domain Tests
   - 27 tests failing
   - Root cause: TaskId.create() method
   - Impact: Blocks Resources domain
   - Agent: @debugger
   - Est: 2-4 hours

2. HIGH: Missing Task-Job Integration
   - No relationship implementation
   - Impact: Can't proceed with scheduling
   - Agent: @implementation-specialist
   - Est: 4-6 hours
```

## Implementation Notes

This command:

1. Lives in `.claude/commands/log.md` following Claude Code conventions
2. Can be invoked directly with `/log` in any Claude session
3. Maintains state by reading/writing to CLAUDE.md and DEVELOPMENT_PLAN.md
4. Provides actionable output with specific agent recommendations
5. Automatically manages context to prevent overflow
6. Tracks lessons learned for future reference

The command is designed to be a true productivity multiplier, reducing context management overhead and ensuring every Claude session starts with clear direction and appropriate agent selection.
