---
description: Async AI software factory - plan, execute, and track Jules-based development
agent: code
---

# Jules Orchestrator Commands

## /plan-work "<prompt>"

Generate execution plan and start orchestration.

**Interactive prompts:**
- Project name (kebab-case)
- Organization
- Tech stack
- Create new repo? (Y/n)

**Actions:**
1. Create GitHub repo with `gh`
2. Create dev branch
3. Generate validated plan with dependency graph
4. Create JULES_MEMORY.json
5. Setup GitHub labels
6. Start background monitoring agent
7. Return immediately with status URL

**Usage:**
```
/plan-work Build a user authentication system with JWT
```

## /jules-verify

Verify setup before execution.

**Checks:**
- GitHub repo exists
- dev branch present
- Jules app installed
- Labels configured
- Memory file accessible

## /jules-start

Start background agent for monitoring.

**Note:** Agent runs in background, polling GitHub every 30s.

## /jules-status

Check current execution status.

**Shows:**
- Project name and progress
- Completed tasks with PR numbers
- Executing tasks (PRs open)
- Pending tasks (waiting dependencies)
- Failed tasks with retry status
- Background agent status

## /jules-resume

Resume orchestration from memory.

**Use when:**
- Agent was stopped
- Session restarted
- Need to recover state

**Actions:**
1. Load JULES_MEMORY.json
2. Reconstruct dependency graph
3. Check existing PRs
4. Start background agent
5. Continue execution

## /jules-stop

Gracefully stop background agent.

**Note:** State is preserved in memory file.

## /jules-retry-failed

Retry failed tasks.

**Actions:**
- Identify tasks with status 'failed' or 'blocked'
- Create new issues with retry labels
- Reset retry count if under max
- Trigger Jules processing

## Configuration

Create `~/.config/kilo/skill/jules-orchestrator/config.yaml`:

```yaml
orchestrator:
  check_interval: 30           # seconds
  max_retries: 2               # max retry attempts
  auto_approve: true           # auto-approve valid PRs
  target_branch: dev           # Jules PRs target
  final_branch: main           # final PR target
  parallel_batches: true       # execute same-level tasks in parallel
  
github:
  bot_username: "jules-bot"
  issue_labels:
    - "jules"
    - "auto-task"
```

## Workflow

```
1. User: /plan-work "Build feature"
      ↓
2. Agent: Interactive setup
      ↓
3. Agent: Create repo, dev branch
      ↓
4. Agent: Generate plan with validation
      ↓
5. Agent: Create memory file
      ↓
6. Agent: Start background agent
      ↓
7. Agent: Create level 0 issues
      ↓
8. Agent: Return immediately
      ↓
9. Background Agent: Poll GitHub
      ↓
10. When deps complete → Create next level issues
      ↓
11. Jules processes → Creates PR to dev
      ↓
12. Background Agent: Validates → Approves → Merges
      ↓
13. Repeat until all tasks complete
      ↓
14. Background Agent: Create final PR (dev → main)
      ↓
15. User: Review and merge final PR
```

## State Persistence

State stored in `JULES_MEMORY.json`:
- Project configuration
- Task statuses
- Issue and PR numbers
- Execution log
- Retry counts

File is committed to repo after each update.

## Branch Strategy

```
main (protected)
  ↑
  │ PR: "Complete feature" (human review)
  │
dev (auto-merge)
  ↑
  │ PR #1: T1 merged
  │ PR #2: T2 merged
  │ PR #3: T3 merged
  │ (all auto-approved)
```

## Dependencies

- `gh` CLI installed and authenticated
- Python 3.8+
- Git
- GitHub account with Jules access

## Logs

Background agent logs to `jules-agent.log` in repo.

## Troubleshooting

**Agent not running:**
```
/jules-resume
```

**Task failed:**
- Check `JULES_MEMORY.json` for failure reason
- Review PR comments
- Run `/jules-retry-failed`

**Jules not processing:**
- Verify Jules app installed in repo
- Check issue has `jules` label
- Ensure `jules` label exists

**PR not merging:**
- Check CI status
- Verify branch protection rules
- Manual approval may be required
