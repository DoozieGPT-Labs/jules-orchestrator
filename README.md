<<<<<<< HEAD
# jules-orchestrator
Async AI software factory with background tracking for Google Jules
=======
# Jules Orchestrator v3.0

Async AI software factory with background tracking, dependency resolution, and auto-approval for Google Jules.

## What It Does

Converts high-level prompts into deterministic execution pipelines:

1. **Plan** - Generate structured tasks with dependencies
2. **Schedule** - Create issues only when dependencies complete
3. **Execute** - Background agent monitors and triggers Jules
4. **Approve** - Auto-approve valid PRs and merge to dev
5. **Complete** - Final PR to main for human review

## Installation

```bash
# Clone the skill
git clone https://github.com/DoozieGPT-Labs/jules-orchestrator.git

# Install to Kilo global skills
mkdir -p ~/.config/kilo/skill/jules-orchestrator
cp -r jules-orchestrator/* ~/.config/kilo/skill/jules-orchestrator/

# Add CLI to PATH
echo 'export PATH="$HOME/.config/kilo/skill/jules-orchestrator/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Verify
jules-agent --help
```

## Requirements

- `gh` CLI installed and authenticated
- Python 3.8+
- Git
- GitHub account with Jules access

## Quick Start

```bash
# In Kilo, use the commands:
/plan-work "Build invoice system with PDF generation"
/jules-verify
/jules-start
/jules-status
```

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
[Final PR] dev → main
```

## Commands

| Command | Description |
|---------|-------------|
| `/plan-work "prompt"` | Generate plan and start orchestration |
| `/jules-verify` | Verify setup |
| `/jules-start` | Start background agent |
| `/jules-status` | Check execution status |
| `/jules-resume` | Resume from memory |
| `/jules-stop` | Stop background agent |

## Configuration

Create `~/.config/kilo/skill/jules-orchestrator/config.yaml`:

```yaml
orchestrator:
  check_interval: 30
  max_retries: 2
  auto_approve: true
  target_branch: dev
  final_branch: main
```

## Key Features

- ✅ Non-blocking execution
- ✅ Dependency-aware scheduling
- ✅ Parallel task execution
- ✅ Auto-approve and merge
- ✅ Resume from any point
- ✅ State persistence

## License

MIT
>>>>>>> f11a0e2 (Jules Orchestrator v3.0 - Complete async implementation)
