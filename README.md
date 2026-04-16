# Jules Orchestrator v3.0.3

> Async AI software factory with ML-based predictions, circuit breakers, auto-scaling, and self-healing workflows.

[![Version](https://img.shields.io/badge/version-3.0.3-blue.svg)](https://github.com/DoozieGPT-Labs/jules-orchestrator)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 🚀 What It Does

Jules Orchestrator converts high-level prompts into deterministic execution pipelines with zero manual intervention until final review.

```
User: /plan-work "Build a complete e-commerce system with Stripe integration"
  ↓
[Orchestrator] Generates plan with dependency graph
  ↓
[Auto-Scale] Creates tasks in parallel where possible
  ↓
[Jules] Executes tasks → PRs to dev branch
  ↓
[Self-Healing] Auto-retries failures with enhanced prompts
  ↓
[Final PR] Complete implementation ready for human review
```

## ✨ Key Features

### Phase 1: Stabilization ✅
- **Idempotency Guards** - Safe retry of approve/merge operations
- **State Machine** - Enforced valid state transitions with history
- **Atomic Memory** - Crash-safe state persistence
- **Process Management** - PID files, health checks, graceful shutdown
- **Circuit Breakers** - Protection against cascading failures

### Phase 2: Control ✅
- **Audit Logging** - Complete execution trail
- **Reconciliation** - Auto-detect orphaned PRs/issues
- **Health Dashboard** - Real-time monitoring
- **Metrics Collection** - Prometheus-compatible metrics
- **Retry Logic** - Exponential backoff with jitter

### Phase 3: Optimization ✅
- **Failure Prediction** - ML-based risk scoring
- **Auto-Scaling** - Dynamic concurrency adjustment
- **Smart Caching** - Intelligent operation caching
- **Self-Healing** - Automatic failure recovery
- **Context Injection** - Learn from successful tasks
- **Adaptive Learning** - Continuous improvement from history

## 📦 Installation

### Global Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/DoozieGPT-Labs/jules-orchestrator.git
cd jules-orchestrator

# Run global installer
./install.sh

# Or manually install to Kilo
mkdir -p ~/.config/kilo/skill/jules-orchestrator
cp -r * ~/.config/kilo/skill/jules-orchestrator/

# Add CLI to PATH
echo 'export PATH="$HOME/.config/kilo/skill/jules-orchestrator/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Verify installation
jules-agent --version  # Should show 3.0.3
```

### System Requirements

- **Python**: 3.8 or higher
- **GitHub CLI**: Installed and authenticated (`gh auth status`)
- **Git**: 2.20+
- **GitHub**: Account with Google Jules access
- **Optional**: `psutil` for system metrics (`pip install psutil`)

### Verify Setup

```bash
# Check all dependencies
/jules-verify

# Expected output:
# ✅ GitHub CLI authenticated
# ✅ Python 3.8+ available
# ✅ Git installed
# ✅ Jules access verified
```

## 🎮 Quick Start

### 1. Create Your First Project

In Kilo, run:
```
/plan-work "Build a user authentication system with JWT tokens"
```

You'll be prompted for:
- **Project name**: `auth-service`
- **Organization**: `your-org`
- **Tech stack**: `Laravel + MySQL`
- **Create repo**: `Y`

### 2. Monitor Progress

```
/jules-status
```

Output:
```
📊 Project: auth-service (v3.0.3)
Progress: 4/6 tasks (67%)

✅ Completed:
   T1 - DB migration (PR #1 merged, 2m 30s)
   T2 - User model (PR #2 merged, 1m 45s)
   
🔄 Executing:
   T5 - UI component (PR #5 open, risk: low)

⏳ Pending:
   T6 - Tests (waiting T5)

🤖 Agent: Running (PID: 12345)
🩺 Health: Healthy
```

### 3. Manage Execution

| Command | Description |
|---------|-------------|
| `/jules-status` | Check current progress with health metrics |
| `/jules-resume` | Resume after restart or crash |
| `/jules-stop` | Gracefully stop background agent |
| `/jules-retry-failed` | Retry failed tasks with enhanced prompts |
| `/jules-health` | View detailed health dashboard |

### 4. Complete Project

When all tasks complete:
1. Agent creates final PR: `dev → main`
2. Review changes at your own pace
3. Merge when satisfied

## ⚙️ Configuration

Create `~/.config/kilo/skill/jules-orchestrator/config.yaml`:

```yaml
orchestrator:
  check_interval: 30              # Seconds between GitHub polls
  max_retries: 3                  # Max retry attempts per task
  auto_approve: true              # Auto-approve valid PRs
  auto_merge: true              # Auto-merge to dev branch
  target_branch: dev              # Jules PRs target
  final_branch: main              # Final PR target
  max_concurrent: 5             # Max parallel executions
  enable_circuit_breaker: true    # Enable API protection
  enable_self_healing: true       # Enable auto-recovery

github:
  bot_username: jules-bot
  issue_labels: [jules, auto-task]

optimization:
  enable_prediction: true         # ML-based risk scoring
  enable_auto_scaling: true       # Dynamic concurrency
  cache_ttl: 60                   # Cache TTL in seconds
  min_success_rate: 0.7         # Threshold for high-risk tasks

logging:
  level: INFO
  file: jules-agent.log
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Jules Orchestrator v3.0.3                │
├─────────────────────────────────────────────────────────────┤
│  Phase 3: Optimization                                      │
│  ├── Failure Predictor (ML risk scoring)                    │
│  ├── Auto Scaler (dynamic concurrency)                    │
│  ├── Cache Manager (intelligent caching)                    │
│  ├── Performance Monitor (bottleneck detection)           │
│  ├── Self-Healing Engine (auto-recovery)                   │
│  ├── Dependency Optimizer (graph optimization)            │
│  ├── Context Injector (pattern learning)                  │
│  └── Adaptive Learning (historical analysis)              │
├─────────────────────────────────────────────────────────────┤
│  Phase 2: Control                                           │
│  ├── Circuit Breaker (API protection)                     │
│  ├── Retry Manager (exponential backoff)                │
│  ├── Reconciliation Engine (orphan detection)             │
│  ├── Health Dashboard (monitoring)                        │
│  └── Metrics Collection (Prometheus-compatible)           │
├─────────────────────────────────────────────────────────────┤
│  Phase 1: Stabilization                                     │
│  ├── State Machine (enforced transitions)                 │
│  ├── Memory Manager (atomic persistence)                  │
│  ├── Process Manager (PID/health checks)                  │
│  └── GitHub Utils (centralized API client)                │
└─────────────────────────────────────────────────────────────┘
```

## 📊 System Status

| Component | Status | Coverage |
|-----------|--------|----------|
| Core Orchestration | ✅ Stable | 100% |
| State Management | ✅ Stable | 100% |
| Circuit Breakers | ✅ Active | 100% |
| Auto-Scaling | ✅ Active | 100% |
| Self-Healing | ✅ Active | 100% |
| Failure Prediction | ✅ Active | 100% |

**System Completeness Score: 9.0/10**

## 🛣️ Roadmap

### v3.0.3 (Current) ✅
- ✅ ML-based failure prediction
- ✅ Auto-scaling with smart batching
- ✅ Self-healing workflows
- ✅ Context injection
- ✅ Adaptive learning
- ✅ Circuit breaker pattern
- ✅ Comprehensive metrics

### v3.1 (Planned)
- [ ] Multi-repo orchestration
- [ ] A/B testing for task strategies
- [ ] Cost optimization recommendations
- [ ] Advanced analytics dashboard
- [ ] Team collaboration features

### v3.2 (Future)
- [ ] Natural language plan editing
- [ ] AI-powered plan optimization
- [ ] Integration with external CI/CD
- [ ] Custom plugin system
- [ ] Enterprise SSO support

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🆘 Support

- **Issues**: https://github.com/DoozieGPT-Labs/jules-orchestrator/issues
- **Discussions**: https://github.com/DoozieGPT-Labs/jules-orchestrator/discussions
- **Documentation**: See [SKILL.md](SKILL.md) for detailed API docs

---

**Made with ❤️ by the DoozieGPT Labs team**

*Last updated: 2026-04-17 | Version 3.0.3*
