# Jules Orchestrator v2 Migration Guide

## Phase 1 Stabilization Complete ✅

### What's New in v2

| Feature | v1 | v2 | Impact |
|---------|----|----| ------|
| File Locking | ❌ | ✅ | Prevents concurrent runs |
| Atomic Writes | ❌ | ✅ | Prevents corruption |
| Retry Logic | ❌ | ✅ | Handles transients |
| Graceful Shutdown | ❌ | ✅ | Safe Ctrl+C |
| Audit Logging | ❌ | ✅ | Full traceability |
| State Validation | ❌ | ✅ | Schema checks |
| Backup Files | ❌ | ✅ | Recovery support |

### Quick Start

```bash
# 1. Generate plan (same as before)
/jules-plan "Build mini ERP with inventory management"

# 2. Use v2 orchestrator (NEW)
cd your-project
python3 ~/.config/kilo/skill/jules-orchestrator/bin/jules-sequential-v2 \
  --repo your-org/your-project
```

### Migration from v1

If you have an existing project with JULES_MEMORY.json:

```bash
cd your-project

# Option 1: Just start using v2 (backwards compatible)
python3 ~/.config/kilo/skill/jules-orchestrator/bin/jules-sequential-v2 \
  --repo your-org/your-project

# v2 will:
# - Read existing JULES_MEMORY.json
# - Create .lock file for exclusive access
# - Create .backup files for safety
# - Write audit.log for traceability
```

### Safety Features

#### 1. Process Mutex
```python
# v2 creates a lock file
JULES_MEMORY.lock  # flock-based

# Prevents:
# - Two terminals running simultaneously
# - Race conditions on state file
# - Corrupted JULES_MEMORY.json
```

#### 2. Atomic Writes
```python
# v2 writes process:
1. Write to .tmp.JULES_MEMORY.json.PID
2. Create backup: JULES_MEMORY.json.backup
3. Atomic rename: .tmp → JULES_MEMORY.json

# Prevents:
# - Corruption on crash
# - Partial writes
# - Lost updates
```

#### 3. Retry with Backoff
```python
# GitHub API calls retry:
Attempt 1: immediate
Attempt 2: after 2s
Attempt 3: after 4s

# Handles:
# - GitHub 500 errors
# - Network blips
# - Rate limiting
```

#### 4. Graceful Shutdown
```bash
# Press Ctrl+C during execution:

^C
[2024-01-15 10:30:00] [INFO] Received signal 2, shutting down gracefully...
[2024-01-15 10:30:00] [INFO] Task T1 still in progress

# Run again to resume:
python3 jules-sequential-v2 --repo org/project

# Resumes from saved state
```

#### 5. Audit Logging
```
# audit.log created:
{"timestamp": "2024-01-15T10:30:00", "task_id": "T1", "event": "issue_created", "details": {"issue_id": 10}}
{"timestamp": "2024-01-15T10:35:00", "task_id": "T1", "event": "task_complete", "details": {"pr_number": 15}}
```

### Recovery Scenarios

#### Scenario 1: Crash During Save
```bash
# Symptom: JULES_MEMORY.json is empty or corrupted

# Recovery:
# v2 automatically loads from backup:
JULES_MEMORY.json.backup

# If backup also corrupted:
# Check git history:
git checkout HEAD -- JULES_MEMORY.json
```

#### Scenario 2: Lock File Left Behind
```bash
# Symptom: "Another instance is running" but none is

# Recovery:
rm JULES_MEMORY.lock
# Then restart
```

#### Scenario 3: Task Failed
```bash
# Symptom: Task in failed_tasks list

# Recovery options:
# 1. Reset and retry (manual):
# Edit JULES_MEMORY.json:
# - Move T3 from failed_tasks to pending_tasks
# - Clear current_task

# 2. Delete issue and retry:
gh issue close <issue_number>
# Then restart orchestrator
```

### Configuration

v2 uses sensible defaults but can be configured:

```python
# In jules-sequential-v2 (edit directly):
self.config = {
    'jules_timeout_minutes': 15,    # How long to wait for Jules
    'max_retries': 3,                # API retry attempts
    'retry_base_delay': 1.0,         # Initial retry delay
    'poll_interval': 30,             # Seconds between polls
}
```

### File Structure

After running v2:

```
project/
├── JULES_MEMORY.json           # State file (atomic writes)
├── JULES_MEMORY.json.backup    # Latest backup
├── JULES_MEMORY.lock           # Process lock
├── jules-orchestrator.log      # Execution log
├── audit.log                   # Audit trail
└── .tmp.JULES_MEMORY.json.*    # Temp files (auto-cleaned)
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| "Another instance is running" | `rm JULES_MEMORY.lock` |
| Corrupted JULES_MEMORY.json | `git checkout HEAD -- JULES_MEMORY.json` |
| Task stuck in current_task | Edit file: set `"current_task": null` |
| Jules never completes | Check issue manually: `gh issue view <id>` |
| PR merge fails | Merge manually: `gh pr merge <number>` |

### Performance

| Metric | v1 | v2 | Note |
|--------|----|----|------|
| Startup | Instant | ~50ms | Lock acquisition |
| Save | ~1ms | ~5ms | Atomic + backup |
| Poll | 30s | 30s | Configurable |
| Recovery | Manual | Automatic | From backup |

### When to Use v1 vs v2

**Use v2 (jules-sequential-v2):**
- Production projects
- Team collaboration
- Long-running executions
- When reliability matters

**Use v1 (jules-sequential):**
- Quick demos
- Personal experiments
- When debugging v2 issues
- Legacy compatibility

**Use jules-agent:**
- Parallel execution needed
- Independent tasks
- Speed over safety
- CI/CD pipelines

### Next Steps (Phase 2)

After Phase 1 stabilizes:

1. **State Machine Enforcement** - Validate all transitions
2. **Health Dashboard** - Visual progress tracking
3. **Notifications** - Slack/email alerts
4. **Auto-Reconciliation** - Self-healing
5. **Time-Travel** - Rollback to any state

### Feedback

Issues or suggestions:
- Check logs: `tail -f jules-orchestrator.log`
- Review audit: `cat audit.log | jq .`
- Report bugs: Include state file and logs
