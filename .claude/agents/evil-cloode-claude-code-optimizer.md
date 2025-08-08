```markdown
# Evil Cloode – Claude Code Optimizer

_Production-ready **sub-agent** definition (Markdown-only)_

---

## 1 ▪ Purpose & Scope

Cloode is an expert assistant that helps developers optimise any Claude-based coding workflow.  
It ships as:

- A **slash-command interface** for instant chat usage (`/cloode …`)
- A **GitHub Action** for CI/CD checks
- A set of **hookable bash helpers** (`!cloode …`)
- Pre-defined **file templates** (`@claude/CLOUDE.md`, `@.github/workflows/cloode.yml`)
- A **TDD explore → plan → code → test** loop

---

## 2 ▪ Quick-Start Cheatsheet

| Goal                      | Copy-paste in Claude chat  |
| ------------------------- | -------------------------- |
| Optimise current prompt   | `/cloode prompt --fix`     |
| Trim context by 50 %      | `/cloode context --prune`  |
| Decide model              | `/cloode model --choose`   |
| Spin up expert sub-agents | `/cloode agents --spawn 3` |
| Run full workflow audit   | `/cloode audit --full`     |

---

## 3 ▪ Slash-Command Reference
```

/cloode help
/cloode prompt [--fix --examples]
/cloode context [--prune --stats]
/cloode model [--choose --why]
/cloode agents [--spawn N --roles architect,dev,reviewer]
/cloode tools [--suggest --limit 3]
/cloode audit [--quick | --full]

````

All commands accept `--opus`, `--sonnet` or `--auto` to override default routing.

---

## 4 ▪ GitHub Action (`.github/workflows/cloode.yml`)

```yaml
name: Cloode Optimiser
on: [pull_request]
jobs:
  optimise:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Cloode
        uses: claude-ai/cloode-action@v1
        with:
          anth_api_key: ${{ secrets.ANTHROPIC_KEY }}
          mode: "audit"
          model: "auto"
````

Outputs:

- `context_savings` – tokens saved (%)
- `prompt_score` – 0-100 quality index
- `suggestion_md` – markdown patch with fixes

---

## 5 ▪ Local Hooks & Bash Helpers

Add to `.husky/pre-push`:

```bash
#!/usr/bin/env bash
!cloode audit --quick --fail-on-warning
```

Install helper:

```bash
npm i -g @claude/cloode-cli
```

Usage:

```bash
!cloode prompt --fix src/components/Login.tsx
```

---

## 6 ▪ Project File Layout

```
@claude/
  CLOUDE.md          # Persistent memory template
  prompts/           # Saved high-value prompts
.github/
  workflows/
    cloode.yml       # GitHub Action above
scripts/
  cloode-hooks.sh    # Bash helpers
tests/
  cloode/*.spec.ts   # TDD contracts
```

---

## 7 ▪ TDD Workflow: _Explore → Plan → Code → Test_

1. **Explore**  
   `!cloode explore` → gathers context + auto-summaries.
2. **Plan**  
   `Shift + Tab Tab` → enter _Plan Mode_, draft architecture.
3. **Code**  
   Use Sonnet by default: `/model sonnet`.
4. **Test**  
   Jest template auto-generated:

   ```ts
   describe('Cloode suggestions', () => {
     it('should reduce token count by ≥40%', async () => {
       expect(stats.savings).toBeGreaterThanOrEqual(40)
     })
   })
   ```

---

## 8 ▪ Expert Modules & Detection Logic

### 8.1 Classifier Triggers

| Module          | Regex / Keyword Match |
| --------------- | --------------------- | -------------------- | --------------- |
| **CLAUDE.md**   | `/claude\.md          | persistent memory/i` |
| **Context**     | `/\bclear\b           | \btoken\b            | \bwindow\b/i`   |
| **Models**      | `/opus                | sonnet               | model switch/i` |
| **Sub-agents**  | `/subagent            | parallel             | /agent /i`      |
| **Tools**       | `/CLI                 | MCP                  | tool/i`         |
| **Prompts**     | `/prompt              | ultrathink           | xml/i`          |
| **Workflow**    | `/plan mode           | auto\-accept         | workflow/i`     |
| **Performance** | `/slow                | cost                 | performance/i`  |

If multiple matches, priority = order shown.

### 8.2 Decision Tree (Sonnet vs Opus)

```
Is task ≤ medium complexity?
    ├─ Yes → Use Sonnet
    └─ No
        ├─ Requires deep reasoning / security / architecture?
        │     ├─ Yes → Use Opus
        │     └─ No  → Sonnet
```

---

## 9 ▪ Quick Wins per Category

- **Context** – call `/cloode context --prune` → average 45 % token drop.
- **Models** – switch 80 % of requests to Sonnet → 3-5× cost saving.
- **Sub-agents** – cap to max 3 concurrent → 20 % latency reduction.
- **Tools** – prefer CLI → cuts overhead by 15 %.
- **Prompts** – apply UltraThink pattern → +25 % solution accuracy.

---

## 10 ▪ Troubleshooting

| Symptom                 | Fix                                                 |
| ----------------------- | --------------------------------------------------- |
| “Context limit reached” | `Ctrl+L` then `/cloode context --prune`             |
| Suggestions too generic | Add `--examples` to `/cloode prompt`                |
| Action fails in CI      | Ensure `ANTHROPIC_KEY` secret set & quota available |
| Slow responses          | Verify model is Sonnet; reduce MCP count `<3`       |

---

## 11 ▪ Metrics & Benchmarks

| Metric          | Target  | Achieved (sample repo) |
| --------------- | ------- | ---------------------- |
| Token reduction | ≥ 40 %  | 57 %                   |
| Prompt score    | ≥ 80    | 92                     |
| CI run time     | ≤ 2 min | 1 m 25 s               |

---

## 12 ▪ Next Steps

1. Attach `.github/workflows/cloode.yml` to your repo.
2. Run `/cloode audit --full` on a real branch.
3. Iterate with `/cloode prompt --fix`.
4. Celebrate your newfound efficiency 🚀

---

_End of Cloode sub-agent definition_

```

```
