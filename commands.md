# Jules Orchestrator Commands

Commands for the Jules AI software factory - sequential task execution via GitHub Issues.

## Commands

### `/jules-plan "<prompt>"`

Generate execution plan and initialize project for Jules orchestration.

**Usage:**
```
/jules-plan "Build mini ERP with inventory, purchase orders, vendor management"
```

**Interactive Setup:**
- Asks for GitHub organization
- Asks for project name (kebab-case)
- Asks for tech stack
- Creates GitHub repo with `gh`
- Sets up `dev` and `main` branches
- Creates GitHub labels (jules, auto-task, db, api, ui, test)
- Generates JULES_MEMORY.json
- Commits memory file to repo

**Output:**
```
✅ Repo created: https://github.com/org/project
✅ Plan generated: 9 tasks
✅ Labels created
✅ Orchestrator installed

To start:
  python3 ~/.config/kilo/skill/jules-orchestrator/bin/jules-sequential --repo org/project
```

**Plan Structure:**
- Tasks with dependencies (DB → API → UI → Test)
- Acceptance criteria for each task
- Test cases
- Files expected

### `jules-sequential --repo <org/name>`

**Start sequential execution** - creates ONE issue at a time, waits for Jules completion.

**Behavior:**
1. Finds first task with dependencies met
2. Creates GitHub issue with `jules` label (auto-triggers Jules)
3. Polls every 30 seconds for Jules completion
4. Auto-merges PR when ready
5. Marks task complete
6. Triggers next task
7. Repeats until all done

**Key Feature:** Only ONE task executes at a time (sequential, not parallel).

### `jules-agent --repo <org/name> start`

**Start background agent** - the original async orchestrator with batch processing.

**Note:** This creates ALL ready issues at once (parallel). Use `jules-sequential` for strict sequential execution.

### `jules-agent --repo <org/name> status`

Check execution status and progress.

## How It Works

### Sequential Orchestrator (Recommended)
```
User runs: jules-sequential --repo org/project

Loop:
  ┌─────────────────────────────────────┐
  │ Find next ready task (deps met)     │
  │                                     │
  │ Create GitHub issue + jules label   │ ──→ Jules auto-triggers
  │                                     │
  │ Poll every 30s for completion:      │
  │   - Check for Jules comment         │
  │   - Look for PR creation            │
  │   - Wait for PR merge               │
  │                                     │
  │ Mark task complete                  │
  │                                     │
  │ Save JULES_MEMORY.json              │
  │                                     │
  │ Repeat for next task                │
  └─────────────────────────────────────┘
```

### State Machine
- `pending` → `issue_created` → `jules_triggered` → `pr_opened` → `approved` → `merging` → `complete`
- One task moves through states at a time
- Next task only starts after previous is `complete`

## File Structure

```
~/.config/kilo/skill/jules-orchestrator/
├── bin/
│   ├── jules-agent          # Background async orchestrator
│   ├── jules-sequential     # Sequential orchestrator (NEW)
│   └── jules-plan           # CLI plan generator (NEW)
├── lib/
│   ├── background_agent.py  # Main orchestrator logic
│   ├── state_machine.py     # Task state management
│   ├── github_utils.py      # GitHub API helpers
│   └── ...
└── SKILL.md                 # Full documentation
```

## Task Requirements

Each task MUST have:
- `id`: T1, T2, etc.
- `type`: DB, API, UI, Refactor, Test
- `dependencies`: List of task IDs
- `files_expected`: Exact file paths
- `acceptance_criteria`: Testable conditions
- `test_cases`: What to verify

## JULES_MEMORY.json

State file tracking:
- Project metadata
- Task definitions
- Execution status
- Completed/failed/pending lists
- PR references

## Troubleshooting

**Jules not triggering?**
- Check `jules` label exists on repo
- Verify Jules GitHub App is installed
- Check issue body has proper format

**Tasks stuck?**
- Check `jules-agent.log` for details
- Verify GitHub token has permissions
- Check if PR was created manually

**Want to restart?**
- Delete JULES_MEMORY.json
- Or mark tasks complete manually
- Or delete and recreate repo
