---
name: jules-orchestrator
version: 3.0.0
description: Async AI software factory with background tracking, dependency resolution, and auto-approval for Google Jules
source: kilocode-complete
author: Claude Code Team
---

# Jules Orchestrator v3.0

## Philosophy

> **Agent owns: Planning, orchestration, tracking, memory, dependency resolution, PR approval**  
> **Jules owns: Implementation only**  
> **Flow: Async parallel execution with dependency-aware scheduling**

## What It Does

Converts high-level prompts into deterministic execution pipelines:
1. **Plan** - Generate structured tasks with dependencies
2. **Schedule** - Create issues only when dependencies complete  
3. **Execute** - Background agent monitors and triggers Jules
4. **Approve** - Auto-approve valid PRs and merge to dev
5. **Complete** - Final PR to main for human review

## Commands

### `/plan-work "<prompt>"`
Generate execution plan and start orchestration.

**Example:**
```
/plan-work Build a user authentication system with JWT tokens
```

**Flow:**
1. Interactive prompts (project name, org, tech stack)
2. Create GitHub repo with `gh`
3. Create dev branch
4. Generate validated plan
5. Create JULES_MEMORY.json
6. Setup labels
7. Start background agent
8. Return immediately with tracking URL

### `/jules-verify`
Verify setup before execution.

**Checks:**
- Repo exists
- dev branch exists
- Jules installed
- Labels configured
- Memory file accessible

### `/jules-start`
Start/resume background agent.

### `/jules-status`
Check execution status.

**Output:**
```
Project: invoice-manager
Progress: 4/6 tasks (67%)

✅ Completed:
   T1 - DB migration (PR #1 merged)
   
🔄 Executing:
   T5 - UI component (PR #5 open)

⏳ Pending:
   T6 - Tests (waiting T5)

Background Agent: Running
Last Update: 2 min ago
```

### `/jules-resume`
Resume from memory after restart.

### `/jules-stop`
Stop background agent gracefully.

## Architecture

```
User: /plan-work
  ↓
[Agent] Interactive setup
  ↓
[GitHub] Create repo + dev branch
  ↓
[Planner] Generate plan with validation
  ↓
[Memory] JULES_MEMORY.json created
  ↓
[Background Agent Started]
  ↓
[Monitor] Poll GitHub every 30s
  ↓
[Dependency Resolver] Check ready tasks
  ↓
[Create Issues] For level N when level N-1 complete
  ↓
[Jules] Execute → PR to dev
  ↓
[Validator] Check PR against criteria
  ↓
[Approver] Auto-approve valid PRs
  ↓
[Merger] Merge to dev
  ↓
[Repeat until all complete]
  ↓
[Final PR] dev → main
```

## State Machine

```
pending → issue_created → jules_triggered → pr_opened → validating → approved → merging → merged → complete
                                                                          ↓
                                                                    failed → retry → blocked
```

## Key Features

- ✅ **Non-blocking** - Returns immediately, runs in background
- ✅ **Dependency-aware** - Tasks created only when deps complete
- ✅ **Parallel execution** - Tasks at same level run simultaneously
- ✅ **Auto-approval** - Valid PRs approved and merged to dev
- ✅ **Resume** - Can resume after agent restart
- ✅ **Branch strategy** - dev ← Jules PRs, main ← final PR
- ✅ **State persistence** - Memory committed to repo

## Configuration

Environment variables:
- `GITHUB_TOKEN` - GitHub API token
- `JULES_API_KEY` - Google Jules API key

Optional in `~/.config/kilo/skill/jules-orchestrator/config.yaml`:
```yaml
orchestrator:
  check_interval: 30
  max_retries: 2
  auto_approve: true
  target_branch: dev
  final_branch: main
```

## Installation

```bash
# Copy to global skills
mkdir -p ~/.config/kilo/skill/jules-orchestrator
cp -r /path/to/jules-orchestrator/* ~/.config/kilo/skill/jules-orchestrator/

# Verify
kilo --skills
```

## Files

```
jules-orchestrator/
├── SKILL.md                    # This file
├── command.md                  # Kilo command definition
├── bin/
│   └── jules-agent            # CLI entry point
├── lib/
│   ├── __init__.py
│   ├── background_agent.py     # Main background agent
│   ├── dependency_resolver.py  # Dependency graph
│   ├── plan_validator.py       # Plan validation
│   ├── github_utils.py         # GitHub API helpers
│   ├── resume_logic.py         # Resume from memory
│   └── memory_manager.py       # Memory persistence
└── templates/
    ├── issue_body.md           # Issue template
    ├── jules_prompt.txt        # Jules prompt template
    └── final_pr_body.md        # Final PR template
```

## Example Session

```
User: /plan-work "Build invoice system with PDF"

Agent: 🚀 Jules Orchestrator v3.0

Step 1/7: Project Setup
- Name: invoice-system
- Org: DoozieGPT-Labs  
- Tech: Laravel + MySQL
- Create repo? [Y/n]: Y
✅ Created: https://github.com/DoozieGPT-Labs/invoice-system

Step 2/7: Create Branches
✅ dev branch created

Step 3/7: Generate Plan
✅ 6 tasks generated
✅ Validation passed

Step 4/7: Create Memory
✅ JULES_MEMORY.json created

Step 5/7: Setup Labels
✅ 6 labels created

Step 6/7: Start Background Agent
✅ Agent started (PID: 12345)

Step 7/7: Create Initial Issues
✅ T1: DB migration
✅ T2: Invoice model

🎉 Orchestration started!

Track: /jules-status
Repo: https://github.com/DoozieGPT-Labs/invoice-system
```

## Success Criteria

- Predictable outputs
- >80% PR success rate
- Non-blocking execution
- Automatic retry on failure
- Resume from any point
- Zero manual intervention until final review

---

*Complete Async Implementation - Agent Driven, Dependency Aware, Non-Blocking*
