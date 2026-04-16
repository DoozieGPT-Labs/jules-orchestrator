# Tool-Agnostic Usage Guide

> Use Jules Orchestrator with any AI coding assistant

Jules Orchestrator v3.0.3+ includes a **tool-agnostic adapter system** that automatically detects which AI coding assistant you're using and adapts commands accordingly.

## Supported Tools

| Tool | Detection Method | Command Style |
|------|-----------------|---------------|
| **Kilo** | `~/.config/kilo/` exists, `KILO_VERSION` env | `/command` |
| **OpenCode** | `~/.opencode/` exists, `OPENCODE_VERSION` env | `@command` |
| **Claude Code** | `~/.claude/` exists, `CLAUDE_CODE_VERSION` env | Natural language |
| **Cursor** | `~/.cursor/` exists, `.cursor` directory | Cmd+Shift+P palette |
| **Generic CLI** | Any terminal/shell environment | Direct CLI |

## Quick Start (Universal)

```bash
# 1. Clone and install
git clone https://github.com/DoozieGPT-Labs/jules-orchestrator.git
cd jules-orchestrator
./install.sh global

# 2. Reload shell
source ~/.zshrc  # or ~/.bashrc

# 3. The 'jules' command auto-detects your environment
jules detect
```

## Tool-Specific Usage

### Kilo

**Detection:** Automatically detected when running under Kilo

**Installation:**
```bash
# Standard Kilo skill installation
mkdir -p ~/.config/kilo/skill/jules-orchestrator
cp -r jules-orchestrator/* ~/.config/kilo/skill/jules-orchestrator/
echo 'export PATH="$HOME/.config/kilo/skill/jules-orchestrator/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**Commands:**
```
/plan-work "Build a REST API with authentication"
/jules-status
/jules-resume
/jules-verify
/jules-health
```

**Behind the scenes:** The tool adapter translates `/command` to the appropriate format

### OpenCode

**Detection:** Automatically detected when running under OpenCode

**Installation:**
```bash
# Install as OpenCode extension
mkdir -p ~/.opencode/extensions/jules-orchestrator
cp -r jules-orchestrator/* ~/.opencode/extensions/jules-orchestrator/
chmod +x ~/.opencode/extensions/jules-orchestrator/bin/jules
```

**Commands:**
```
@jules plan-work "Build a REST API"
@jules status
@jules resume
@jules verify
```

**Alternative - Direct CLI:**
```bash
jules plan "Build a REST API" --repo owner/repo
jules status --repo owner/repo
jules resume --repo owner/repo
```

### Claude Code

**Detection:** Automatically detected when running under Claude Code

**Installation:**
```bash
# Install as Claude skill
mkdir -p ~/.claude/skills/jules-orchestrator
cp -r jules-orchestrator/* ~/.claude/skills/jules-orchestrator/
chmod +x ~/.claude/skills/jules-orchestrator/bin/jules
```

**Commands:**
```
Jules: plan work for "Build a REST API with authentication"
Jules: show status
Jules: resume orchestration
Jules: verify setup
```

**Or use directly:**
```bash
~/.claude/skills/jules-orchestrator/bin/jules plan "Build API" --repo owner/repo
```

### Cursor

**Detection:** Automatically detected when running under Cursor

**Installation:**
```bash
# Install as Cursor extension
mkdir -p ~/.cursor/extensions/jules-orchestrator
cp -r jules-orchestrator/* ~/.cursor/extensions/jules-orchestrator/
chmod +x ~/.cursor/extensions/jules-orchestrator/bin/jules
```

**Commands:**
```
Cmd+Shift+P → "Jules: Plan Work" → "Build a REST API"
Cmd+Shift+P → "Jules: Show Status"
Cmd+Shift+P → "Jules: Resume"
```

**Or use directly:**
```bash
~/.cursor/extensions/jules-orchestrator/bin/jules plan "Build API" --repo owner/repo
```

### Generic CLI (Any Terminal)

**Works in:** Any terminal, shell, or CI/CD pipeline

**Installation:**
```bash
# Global installation
git clone https://github.com/DoozieGPT-Labs/jules-orchestrator.git
cd jules-orchestrator
./install.sh global

# Or manual
mkdir -p ~/.jules-orchestrator
cp -r jules-orchestrator/* ~/.jules-orchestrator/
ln -s ~/.jules-orchestrator/bin/jules /usr/local/bin/jules
```

**Commands:**
```bash
# Plan new work
jules plan "Build a REST API with authentication" --repo owner/repo

# Check status
jules status --repo owner/repo

# Resume agent
jules resume --repo owner/repo

# Verify setup
jules detect

# Show installation guide
jules install
```

## The Tool Adapter System

### How It Works

```python
# The orchestrator auto-detects the environment
from tool_adapter import get_adapter

orchestrator = get_adapter()
# Returns: KiloAdapter, OpenCodeAdapter, ClaudeCodeAdapter, etc.

# Commands are automatically translated
command = orchestrator.execute("plan_work", prompt="Build API")
# Kilo: "/plan-work \"Build API\""
# OpenCode: "@jules plan-work \"Build API\""
# Claude: "Jules: plan work for \"Build API\""
# Generic: "jules-agent --repo owner/repo"
```

### Force Specific Tool

If auto-detection fails, force a specific tool:

```bash
export JULES_TOOL=opencode
jules plan "Build API"

# Options: kilo, opencode, claude_code, cursor, generic
```

## Universal Command Reference

| Action | Kilo | OpenCode | Claude | Cursor | CLI |
|--------|------|----------|--------|--------|-----|
| Plan Work | `/plan-work` | `@jules plan-work` | `Jules: plan` | Cmd+Shift+P | `jules plan` |
| Check Status | `/jules-status` | `@jules status` | `Jules: status` | Cmd+Shift+P | `jules status` |
| Resume | `/jules-resume` | `@jules resume` | `Jules: resume` | Cmd+Shift+P | `jules resume` |
| Verify | `/jules-verify` | `@jules verify` | `Jules: verify` | Cmd+Shift+P | `jules verify` |
| Health | `/jules-health` | `@jules health` | `Jules: health` | Cmd+Shift+P | `jules health` |

## CI/CD Integration

Works in GitHub Actions, GitLab CI, etc.:

```yaml
# .github/workflows/jules.yml
name: Jules Orchestrator

on:
  workflow_dispatch:
    inputs:
      prompt:
        description: 'Project to build'
        required: true

jobs:
  orchestrate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install Jules
        run: |
          git clone https://github.com/DoozieGPT-Labs/jules-orchestrator.git
          cd jules-orchestrator
          ./install.sh global
      
      - name: Plan Work
        run: |
          jules plan "${{ github.event.inputs.prompt }}" \
            --repo ${{ github.repository }} \
            --tool generic
      
      - name: Start Agent
        run: |
          nohup jules-agent --repo ${{ github.repository }} &
          sleep 5
          jules status --repo ${{ github.repository }}
```

## Docker Support

```dockerfile
FROM python:3.10-slim

RUN apt-get update && apt-get install -y git gh

WORKDIR /app
COPY . .
RUN ./install.sh global

ENV JULES_TOOL=generic
ENTRYPOINT ["jules"]
```

```bash
# Build and run
docker build -t jules-orchestrator .
docker run -it jules-orchestrator plan "Build API" --repo owner/repo
```

## Troubleshooting

### Tool Not Detected

```bash
# Check detection
jules detect

# Force specific tool
export JULES_TOOL=generic
jules plan "Build API"
```

### Commands Not Working

```bash
# Check if in PATH
which jules

# If not, use full path
~/.config/kilo/skill/jules-orchestrator/bin/jules detect

# Or install globally
./install.sh global
source ~/.zshrc
```

### Different Tool Than Expected

```bash
# The adapter prioritizes in this order:
# 1. Kilo
# 2. OpenCode
# 3. Claude Code
# 4. Cursor
# 5. Generic

# Force specific tool
export JULES_TOOL=opencode
jules detect
```

## Migration from Tool-Specific to Tool-Agnostic

If you were using a tool-specific version:

1. **Update your installation:**
   ```bash
   git pull origin main
   ./install.sh global
   ```

2. **Update your commands:**
   - Old: `/plan-work "prompt"`
   - New: `jules plan "prompt"` (auto-translates)
   - Or keep using: `/plan-work` (still works)

3. **No breaking changes** - existing commands still work

## Architecture

```
┌─────────────────────────────────────────┐
│         User Commands                   │
│  /plan-work | @jules | jules plan       │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│      ToolAgnosticOrchestrator           │
│  - Auto-detects environment             │
│  - Selects appropriate adapter          │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│         Tool Adapters                   │
│  ┌──────────┐ ┌──────────┐            │
│  │ Kilo     │ │ OpenCode │            │
│  │ Adapter  │ │ Adapter  │            │
│  └──────────┘ └──────────┘            │
│  ┌──────────┐ ┌──────────┐            │
│  │ Claude   │ │ Cursor   │            │
│  │ Adapter  │ │ Adapter  │            │
│  └──────────┘ └──────────┘            │
│  ┌──────────┐                           │
│  │ Generic  │                           │
│  │ Adapter  │                           │
│  └──────────┘                           │
└─────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│       Jules Orchestrator Core           │
│  - Background Agent                     │
│  - State Machine                        │
│  - Circuit Breakers                     │
│  - Self-Healing                         │
└─────────────────────────────────────────┘
```

## Examples

### Example 1: Using in Kilo

```
User: /plan-work "Build a user authentication system"

[Detected: Kilo environment]
[Translated to: /plan-work command]

Agent: 🚀 Jules Orchestrator v3.0.3
       Detected: Kilo

       Step 1/7: Interactive Setup
       - Name: auth-service
       - Tech: Laravel + MySQL

       ... continues as normal ...
```

### Example 2: Using in OpenCode

```
User: @jules plan-work "Build a user authentication system"

[Detected: OpenCode environment]
[Translated to: Python execution]

Agent: 🚀 Jules Orchestrator v3.0.3
       Detected: OpenCode

       Running: python3 ~/.opencode/extensions/jules-orchestrator/...
       
       Step 1/7: Interactive Setup
       ... continues as normal ...
```

### Example 3: Using in Claude Code

```
User: Jules: plan work for "Build a user authentication system"

[Detected: Claude Code environment]
[Translated to: CLI execution]

Agent: 🚀 Jules Orchestrator v3.0.3
       Detected: Claude Code
       
       Executing: jules plan "Build a user authentication system"
       
       Step 1/7: Interactive Setup
       ... continues as normal ...
```

### Example 4: Direct CLI (Works Everywhere)

```bash
$ jules plan "Build a user authentication system" --repo my-org/auth-service

🚀 Jules Orchestrator v3.0.3
   Detected: Generic CLI

Planning work for: my-org/auth-service
Prompt: Build a user authentication system

Actions:
  1. Generate execution plan
  2. Create GitHub issues
  3. Start background agent
  ...
```

## Summary

The tool-agnostic system means:
- ✅ **One codebase** works across all tools
- ✅ **Automatic detection** of your environment
- ✅ **Consistent commands** with tool-specific syntax
- ✅ **Easy migration** between tools
- ✅ **CI/CD ready** with generic CLI
- ✅ **No breaking changes** to existing usage

**Choose your tool, use Jules!**
