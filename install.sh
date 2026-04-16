#!/bin/bash
#
# Jules Orchestrator Global Installer v3.0.3
# https://github.com/DoozieGPT-Labs/jules-orchestrator
#
# Usage: ./install.sh [global|local|verify]
#   global  - Install to ~/.config/kilo/skill/jules-orchestrator (default)
#   local   - Verify current directory structure
#   verify  - Verify existing installation
#

set -e

# Version
VERSION="3.0.3"
SKILL_NAME="jules-orchestrator"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}➜${NC} $1"; }
print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }

print_banner() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║         Jules Orchestrator v${VERSION} Installer           ║"
    echo "║         Async AI Software Factory                          ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        echo "  Install from: https://python.org"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    print_success "Python $PYTHON_VERSION"
    
    # Check Git
    if ! command -v git &> /dev/null; then
        print_error "Git is not installed"
        exit 1
    fi
    print_success "Git available"
    
    # Check GitHub CLI
    if command -v gh &> /dev/null; then
        print_success "GitHub CLI available"
    else
        print_warning "GitHub CLI not found (optional but recommended)"
    fi
    
    # Check psutil (optional)
    if python3 -c "import psutil" 2>/dev/null; then
        print_success "psutil available (system metrics enabled)"
    else
        print_warning "psutil not installed (system metrics disabled)"
        echo "  Install with: pip3 install psutil"
    fi
}

check_structure() {
    print_status "Verifying skill structure..."
    
    local dir="${1:-$SCRIPT_DIR}"
    local errors=0
    
    # Required files
    local required_files=(
        "SKILL.md"
        "README.md"
        "QUICKSTART.md"
        "config.yaml"
        "bin/jules-agent"
        "lib/__init__.py"
        "lib/background_agent.py"
        "lib/state_machine.py"
        "lib/circuit_breaker.py"
        "lib/retry_manager.py"
        "lib/failure_predictor.py"
        "lib/auto_scaler.py"
    )
    
    for file in "${required_files[@]}"; do
        if [ ! -f "$dir/$file" ]; then
            print_error "Missing: $file"
            ((errors++))
        fi
    done
    
    # Check syntax
    if [ -f "$dir/lib/background_agent.py" ]; then
        if ! python3 -m py_compile "$dir/lib/background_agent.py" 2>/dev/null; then
            print_error "Syntax error in background_agent.py"
            ((errors++))
        fi
    fi
    
    if [ $errors -eq 0 ]; then
        print_success "All required files present"
        return 0
    else
        print_error "$errors files missing or invalid"
        return 1
    fi
}

global_install() {
    TARGET_DIR="$HOME/.config/kilo/skill/$SKILL_NAME"
    
    print_banner
    check_prerequisites
    
    print_status "Installing to: $TARGET_DIR"
    
    # Create directory
    mkdir -p "$TARGET_DIR"
    
    # Copy all files
    print_status "Copying files..."
    cp -r "$SCRIPT_DIR/"* "$TARGET_DIR/"
    
    # Make scripts executable
    chmod +x "$TARGET_DIR/bin/jules-agent"
    
    # Create .jules directories
    mkdir -p "$HOME/.jules/cache"
    mkdir -p "$HOME/.jules/replays"
    mkdir -p "$HOME/.jules/metrics"
    mkdir -p "$HOME/.jules/context"
    
    # Verify structure
    if ! check_structure "$TARGET_DIR"; then
        print_error "Installation verification failed"
        exit 1
    fi
    
    # Add to PATH
    print_status "Configuring PATH..."
    
    SHELL_CONFIG=""
    if [[ "$SHELL" == *"zsh"* ]]; then
        SHELL_CONFIG="$HOME/.zshrc"
    elif [[ "$SHELL" == *"bash"* ]]; then
        SHELL_CONFIG="$HOME/.bashrc"
    else
        SHELL_CONFIG="$HOME/.profile"
    fi
    
    # Check if already in PATH
    if [[ ":$PATH:" != *":$TARGET_DIR/bin:"* ]]; then
        echo "" >> "$SHELL_CONFIG"
        echo "# Jules Orchestrator v${VERSION}" >> "$SHELL_CONFIG"
        echo 'export PATH="'$TARGET_DIR'/bin:$PATH"' >> "$SHELL_CONFIG"
        print_success "Added to PATH in $SHELL_CONFIG"
    else
        print_success "Already in PATH"
    fi
    
    # Success message
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗"
    echo -e "║           Installation Complete! 🎉                   ║"
    echo -e "╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Version:${NC} $VERSION"
    echo -e "${BLUE}Location:${NC} $TARGET_DIR"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo ""
    echo "1. Reload your shell:"
    echo "   source $SHELL_CONFIG"
    echo ""
    echo "2. Verify installation:"
    echo "   jules-agent --version"
    echo ""
    echo "3. Run in Kilo:"
    echo '   /plan-work "Your project description"'
    echo ""
    echo -e "${YELLOW}Documentation:${NC}"
    echo "  • cat $TARGET_DIR/QUICKSTART.md"
    echo "  • cat $TARGET_DIR/README.md"
    echo "  • cat $TARGET_DIR/SKILL.md"
    echo ""
}

verify_install() {
    TARGET_DIR="$HOME/.config/kilo/skill/$SKILL_NAME"
    
    if [ ! -d "$TARGET_DIR" ]; then
        print_error "Not installed globally"
        echo "  Run: ./install.sh global"
        exit 1
    fi
    
    print_banner
    print_status "Verifying installation at: $TARGET_DIR"
    
    if check_structure "$TARGET_DIR"; then
        echo ""
        print_success "Installation verified!"
        echo ""
        echo -e "${BLUE}Version:${NC} $VERSION"
        echo -e "${BLUE}Status:${NC} Ready to use"
        echo ""
        
        # Show available commands
        echo -e "${YELLOW}Available Commands:${NC}"
        echo "  /plan-work \"<prompt>\"  - Start orchestration"
        echo "  /jules-status          - Check status"
        echo "  /jules-resume          - Resume from memory"
        echo "  /jules-verify          - Verify setup"
        echo "  /jules-health          - Health dashboard"
        echo "  /jules-metrics         - View metrics"
        echo ""
    else
        print_error "Installation has issues"
        exit 1
    fi
}

# Main
case "${1:-global}" in
    global)
        global_install
        ;;
    local)
        print_banner
        check_structure
        echo ""
        print_success "Local verification complete"
        echo ""
        echo "To install globally:"
        echo "  ./install.sh global"
        ;;
    verify)
        verify_install
        ;;
    *)
        echo "Usage: $0 [global|local|verify]"
        echo ""
        echo "  global  - Install to ~/.config/kilo/skill/$SKILL_NAME (default)"
        echo "  local   - Verify current directory"
        echo "  verify  - Verify existing installation"
        echo ""
        exit 1
        ;;
esac

echo ""
echo "📖 For help, see: ./QUICKSTART.md"
