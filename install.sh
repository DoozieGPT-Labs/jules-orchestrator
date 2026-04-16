#!/bin/bash
# Jules Orchestrator Skill Installer
# Usage: ./install.sh [global|local]

set -e

SKILL_NAME="jules-orchestrator"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Installing Jules Orchestrator Skill..."
echo ""

# Detect install mode
if [ "$1" = "global" ]; then
    TARGET_DIR="$HOME/.config/kilo/skill/$SKILL_NAME"
    echo "📦 Global install to: $TARGET_DIR"
else
    TARGET_DIR="$PWD"
    echo "📦 Local install (current directory)"
fi

# Create target directory if global
if [ "$1" = "global" ]; then
    mkdir -p "$TARGET_DIR"

    # Copy all files
    echo "📂 Copying skill files..."
    cp -r "$SCRIPT_DIR/"* "$TARGET_DIR/"

    # Make bin executable
    chmod +x "$TARGET_DIR/bin/jules-agent"

    echo ""
    echo "✅ Skill installed globally!"
    echo ""
    echo "Available commands:"
    echo "  /plan-work \"<prompt>\"   - Start orchestration"
    echo "  /jules-status           - Check status"
    echo "  /jules-resume           - Resume from memory"
    echo "  /jules-verify           - Verify setup"
    echo ""
    echo "CLI tool available at: jules-agent"
    echo ""

    # Check if in PATH
    if ! command -v jules-agent &> /dev/null; then
        echo "⚠️  Add to PATH:"
        echo "   export PATH=\"$TARGET_DIR/bin:\$PATH\""
        echo ""
    fi
else
    # Local install - just verify structure
    echo "✓ Verifying skill structure..."

    if [ ! -f "$SCRIPT_DIR/SKILL.md" ]; then
        echo "❌ ERROR: SKILL.md not found"
        exit 1
    fi

    if [ ! -f "$SCRIPT_DIR/bin/jules-agent" ]; then
        echo "❌ ERROR: bin/jules-agent not found"
        exit 1
    fi

    if [ ! -d "$SCRIPT_DIR/lib" ]; then
        echo "❌ ERROR: lib/ directory not found"
        exit 1
    fi

    chmod +x "$SCRIPT_DIR/bin/jules-agent"

    echo ""
    echo "✅ Skill verified!"
    echo ""
    echo "To install globally, run:"
    echo "  ./install.sh global"
    echo ""
fi

echo "📖 See SKILL.md for full documentation"
