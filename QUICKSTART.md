# Quick Start Guide

Get started with Jules Orchestrator in 5 minutes.

## Prerequisites

1. **GitHub CLI** installed and authenticated:
```bash
gh auth status
```

2. **Jules Access** enabled for your GitHub org:
- Go to https://jules.google.com
- Connect your GitHub account
- Install Jules on your organization

3. **Python 3.8+**:
```bash
python3 --version
```

## Installation

```bash
# Clone the skill
git clone https://github.com/DoozieGPT-Labs/jules-orchestrator.git

# Copy to Kilo skills directory
mkdir -p ~/.config/kilo/skill/jules-orchestrator
cp -r jules-orchestrator/* ~/.config/kilo/skill/jules-orchestrator/

# Add CLI to PATH
echo 'export PATH="$HOME/.config/kilo/skill/jules-orchestrator/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

## Your First Project

### Step 1: Plan

In Kilo, run:
```
/plan-work "Build a simple todo API with Laravel"
```

The agent will:
- Ask for project name
- Create GitHub repo
- Generate execution plan
- Start background agent

### Step 2: Verify

```
/jules-verify
```

### Step 3: Check Status

```
/jules-status
```

You'll see:
```
Project: todo-api
Progress: 2/5 tasks (40%)

✅ Completed:
   T1 - DB migration (PR #1 merged)
   
🔄 Executing:
   T3 - API validation (PR #3 open)

⏳ Pending:
   T4 - Tests (waiting T3)

Agent: Running
```

### Step 4: Wait for Completion

The background agent will:
- Monitor GitHub every 30s
- Auto-approve valid PRs
- Merge to dev branch
- Create final PR when complete

### Step 5: Review Final PR

When all tasks complete, the agent creates a PR from `dev` to `main`.

Review and merge manually.

## Common Commands

```
/jules-status     # Check current progress
/jules-resume     # Resume after restart
/jules-stop       # Stop background agent
/jules-retry-failed  # Retry failed tasks
```

## Troubleshooting

**Agent not running?**
```
/jules-resume
```

**Jules not processing?**
- Check issue has `jules` label
- Verify Jules app installed
- Look at jules-agent.log

**PR not merging?**
- Check CI status
- Verify branch protection rules
```

## Next Steps

- Read [SKILL.md](SKILL.md) for detailed documentation
- Check [config.yaml](config.yaml) for configuration options
- Review example plans in the examples/ directory
