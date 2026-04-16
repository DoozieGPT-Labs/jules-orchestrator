# Quick Start Guide

> Get started with Jules Orchestrator in 5 minutes

## ⚡ Prerequisites Check

Before starting, verify you have:

```bash
# Check GitHub CLI (must show authenticated)
gh auth status
# ✅ Logged in to github.com as YOUR_USERNAME

# Check Python version (3.8+)
python3 --version
# ✅ Python 3.8.0+

# Check Git
git --version
# ✅ git version 2.20+
```

**Need GitHub CLI?**
```bash
# macOS
brew install gh
gh auth login

# Linux
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
sudo apt update && sudo apt install gh
gh auth login
```

**Need Jules Access?**
1. Go to https://jules.google.com
2. Sign in with Google
3. Connect your GitHub account
4. Install Jules on your organization

---

## 🚀 Installation (Choose One)

### Option 1: Global Install (Recommended)

```bash
# Clone the repository
git clone https://github.com/DoozieGPT-Labs/jules-orchestrator.git
cd jules-orchestrator

# Run the installer
chmod +x install.sh
./install.sh

# Verify installation
jules-agent --version
# ✅ Jules Orchestrator v4.0.0
```

### Option 2: Kilo Integration

```bash
# Create Kilo skill directory
mkdir -p ~/.config/kilo/skill/jules-orchestrator

# Copy files
cp -r jules-orchestrator/* ~/.config/kilo/skill/jules-orchestrator/

# Add CLI to PATH
echo 'export PATH="$HOME/.config/kilo/skill/jules-orchestrator/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Verify
which jules-agent
# ✅ ~/.config/kilo/skill/jules-orchestrator/bin/jules-agent
```

### Option 3: Development Install

```bash
# Clone with dev dependencies
git clone https://github.com/DoozieGPT-Labs/jules-orchestrator.git
cd jules-orchestrator

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .

# Run from source
python -m lib.background_agent --help
```

---

## 🎯 Your First Project

### Step 1: Create a Project

Open Kilo and run:
```
/plan-work "Build a simple REST API for managing books"
```

**Interactive prompts:**
- **Project name**: `book-api`
- **Organization**: `your-org` (or press Enter for personal)
- **Tech stack**: `Laravel + MySQL` (or `Express + MongoDB`, etc.)
- **Create new repo**: `Y`

**What happens:**
1. ✅ GitHub repo created: `github.com/your-org/book-api`
2. ✅ `dev` branch created
3. ✅ Execution plan generated (5-8 tasks)
4. ✅ Memory file initialized
5. ✅ Background agent started

### Step 2: Monitor Progress

Check status anytime:
```
/jules-status
```

**Example output:**
```
🚀 Jules Orchestrator v4.0.0
📊 Project: book-api
Progress: 3/6 tasks (50%)
Health: ✅ Healthy | Risk: Low

✅ Completed:
   T1 - Database migration (PR #1, 2m 15s)
   T2 - Book model (PR #2, 1m 30s)
   T3 - API routes (PR #3, 2m 45s)

🔄 Executing:
   T4 - Validation layer (PR #4 open)
   Risk Score: 0.3 (Low) | ETA: 3m

⏳ Pending:
   T5 - Tests (waiting T4)
   T6 - Documentation (waiting T5)

🤖 Agent: Running | PID: 12345
📈 Metrics: 95% success rate, 2.3m avg task time
```

### Step 3: Watch It Work

The agent automatically:
- 🔄 Polls GitHub every 30 seconds
- ✅ Validates PRs against acceptance criteria
- 🎉 Auto-approves and merges to `dev`
- 🧠 Learns from successful patterns
- 🩺 Self-heals from failures

**No action needed from you!**

### Step 4: Review Final PR

When complete:
```
🎉 All tasks complete!

Final PR created: https://github.com/your-org/book-api/pull/5
Branch: dev → main

Changes:
- ✅ 6 tasks completed
- ✅ 12 files created
- ✅ All tests passing
- ✅ Quality gate: PASSED (92/100)
```

Review the PR and merge when satisfied.

---

## 🎛️ Common Commands

### Daily Use

```bash
# Check progress
/jules-status

# View health dashboard
/jules-health

# See recent metrics
/jules-metrics

# Pause execution
/jules-stop

# Resume after restart
/jules-resume

# Retry failed tasks
/jules-retry-failed
```

### Advanced Commands

```bash
# Verify setup
/jules-verify

# Check logs
/jules-logs

# Generate report
/jules-report

# Export metrics
/jules-export-metrics
```

---

## 🔧 Troubleshooting

### Agent Not Running?

```bash
# Check if process exists
ps aux | grep jules-agent

# Resume from memory
/jules-resume

# Or manually start
jules-agent --repo your-org/book-api --memory JULES_MEMORY.json
```

### Task Stuck?

```bash
# Check logs
tail -f jules-agent.log

# Common fixes:
# 1. Circuit breaker may have opened - wait 60s
# 2. Rate limit hit - wait for reset
# 3. Jules not processing - check issue labels

# Force reconciliation
/jules-reconcile
```

### PR Not Merging?

```bash
# Check CI status
gh pr checks --repo your-org/book-api

# Common issues:
# 1. CI failing - fix tests first
# 2. Branch protection - verify rules
# 3. Merge conflict - agent will retry
```

### High Risk Tasks?

If you see:
```
⚠️ HIGH RISK: T5 - Payment integration
Risk Score: 0.75
Recommendation: Consider manual review
```

The agent will:
1. Add extra validation
2. Slow down execution
3. Escalate if it fails twice

You can:
```
# Skip if needed
/jules-skip-task T5

# Or manually complete
# Then mark complete in JULES_MEMORY.json
```

---

## 📚 Next Steps

### Learn More

- **Full Documentation**: [SKILL.md](SKILL.md)
- **Architecture**: See system diagram in README.md
- **Configuration**: [config.yaml](config.yaml)

### Customize Behavior

```yaml
# ~/.config/kilo/skill/jules-orchestrator/config.yaml

orchestrator:
  check_interval: 30
  max_retries: 3
  auto_approve: true
  
optimization:
  enable_prediction: true
  enable_auto_scaling: true
  min_success_rate: 0.7
```

### View Examples

```bash
# List example plans
ls examples/

# View a specific example
cat examples/laravel-api.yaml
```

---

## 🎓 Tips for Success

### Writing Good Prompts

✅ **Good:**
```
/plan-work "Build a user authentication system with login, register, password reset using Laravel Sanctum"
```

❌ **Avoid:**
```
/plan-work "Make auth"
```

### Monitoring Health

```bash
# Set up a dashboard alias
alias jules-dashboard='watch -n 5 "jules-agent --status"'

# Check system health
/jules-health | grep -A 5 "Overall Status"
```

### Scaling Up

Once comfortable:
- Try larger projects (10-20 tasks)
- Enable auto-scaling: `max_concurrent: 10`
- Enable self-healing for hands-off operation

---

## 💡 Getting Help

**Quick Help:**
```
/jules-help
```

**Documentation:**
- README.md - Overview and architecture
- SKILL.md - Detailed API documentation
- config.yaml - Configuration reference

**Community:**
- GitHub Issues: https://github.com/DoozieGPT-Labs/jules-orchestrator/issues
- Discussions: https://github.com/DoozieGPT-Labs/jules-orchestrator/discussions

---

**You're ready to go!** 🚀

Start with: `/plan-work "Your project idea here"`
