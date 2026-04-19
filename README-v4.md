# Jules Orchestrator v4.0 - Documentation

## Overview

Production-ready orchestrator for Google Jules with:
- **Phase 1**: File locking, atomic writes, retry logic, graceful shutdown
- **Phase 2**: Schema validation, state machine tracking
- **Phase 3**: Notifications, dashboard, cost tracking (no external deps)

## Installation

Already installed globally in Kilo:
```bash
~/.config/kilo/skill/jules-orchestrator/bin/jules-sequential-v4
```

## Quick Start

### 1. Create a Project

```bash
/jules-plan "Build mini ERP with inventory management"
```

This will:
- Create GitHub repo
- Generate JULES_MEMORY.json
- Setup dev branch
- Create labels

### 2. Run Orchestrator

```bash
cd your-project
python3 ~/.config/kilo/skill/jules-orchestrator/bin/jules-sequential-v4 \
  --repo your-org/your-project
```

### 3. Optional: Configure Features

Create `jules-config.json`:
```json
{
  "notifications": {
    "slack_webhook": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    "slack_channel": "#deployments",
    "enabled": true
  },
  "cost_tracking": {
    "enabled": true,
    "cost_per_hour": 5.0
  },
  "dashboard": {
    "enabled": true,
    "refresh_interval": 30
  },
  "poll_interval": 30,
  "jules_timeout_minutes": 15,
  "auto_merge": true
}
```

## Features

### Core (Always Works)

| Feature | Description |
|---------|-------------|
| File Locking | Prevents concurrent runs via flock |
| Atomic Writes | Prevents corruption on crash |
| Retry Logic | Exponential backoff for API calls |
| Graceful Shutdown | SIGINT/SIGTERM handling |
| Schema Validation | Validates JULES_MEMORY.json |

### Optional (Auto-detects dependencies)

| Feature | Requires | Fallback |
|---------|----------|----------|
| Slack Notifications | urllib | Works with stdlib |
| Webhook Notifications | urllib | Works with stdlib |
| Cost Tracking | None | Always works |
| HTML Dashboard | string.Template | Works with stdlib |

## Commands

### Basic Usage

```bash
# Run with defaults
jules-sequential-v4 --repo org/project

# Custom memory file
jules-sequential-v4 --repo org/project --memory MEMORY.json

# Custom config
jules-sequential-v4 --repo org/project --config my-config.json
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `poll_interval` | 30 | Seconds between polls |
| `jules_timeout_minutes` | 15 | Max wait for Jules |
| `auto_merge` | true | Auto-merge PRs |
| `max_retries` | 3 | API retry attempts |

### Notification Options

| Option | Description |
|--------|-------------|
| `slack_webhook` | Slack incoming webhook URL |
| `slack_channel` | Channel to post to |
| `webhook_url` | Generic webhook URL |

## Architecture

### State Machine

```
PENDING → ISSUE_CREATED → JULES_TRIGGERED → PR_OPENED → COMPLETE
   ↓           ↓               ↓              ↓           ↓
BLOCKED     FAILED          FAILED        FAILED      (terminal)
```

### Safety Guarantees

1. **Process Mutex**: File lock prevents concurrent runs
2. **Atomic Writes**: Write to temp → backup → rename
3. **Retry Logic**: 3 attempts with exponential backoff
4. **Graceful Shutdown**: Complete current poll on SIGINT
5. **Schema Validation**: Catch corrupted state early

### File Structure

```
project/
├── JULES_MEMORY.json              # State file
├── JULES_MEMORY.json.backup       # Latest backup
├── JULES_MEMORY.lock              # Process lock
├── jules-config.json              # Configuration
├── jules-orchestrator.log         # Execution log
├── costs.jsonl                    # Cost tracking
└── .jules-dashboard/
    └── index.html                 # Live dashboard
```

## Troubleshooting

### "Another instance is running"
```bash
rm JULES_MEMORY.lock
```

### Corrupted JULES_MEMORY.json
```bash
# v4 automatically loads from backup
# Or manually:
cp JULES_MEMORY.json.backup JULES_MEMORY.json
```

### Slack not working
- Check webhook URL
- Verify `enabled: true` in config
- Check `jules-orchestrator.log` for errors

### Dashboard not generating
- Check `.jules-dashboard/index.html` exists
- Open with: `open .jules-dashboard/index.html`

## Migration from v2/v3

Just use v4 - it's backwards compatible:
```bash
# Old command (v2)
python3 jules-sequential-v2 --repo org/project

# New command (v4) - same memory file works
python3 jules-sequential-v4 --repo org/project
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `JULES_POLL_INTERVAL` | Override poll interval |
| `JULES_TIMEOUT` | Override Jules timeout |
| `SLACK_WEBHOOK_URL` | Override Slack webhook |

## Cost Tracking

Estimates cost based on execution time:
- Default: $5/hour (Jules API estimate)
- Tracked in `costs.jsonl`
- Summary printed on completion

## Dashboard

Auto-generates HTML dashboard at:
```
.jules-dashboard/index.html
```

Features:
- Live progress bar
- Task status table
- Cost metrics
- Auto-refresh (30s default)
- Links to GitHub issues/PRs

## Notifications

Events notified:
- `start`: Orchestrator started
- `progress`: Task completed
- `failure`: Task failed
- `complete`: All tasks done

## Version History

| Version | Status | Notes |
|---------|--------|-------|
| **v4.0** | ✅ **CURRENT** | Production ready |
| v3.0 | Deprecated | Import issues |
| v2.1 | Deprecated | Use v4 |
| v2.0 | Legacy | Basic features |
| v1.0 | Legacy | No safety |

## Support

- Check logs: `tail -f jules-orchestrator.log`
- Review costs: `cat costs.jsonl | jq .`
- Test config: `python3 -m json.tool jules-config.json`

## License

MIT - Part of Everything Claude Code
