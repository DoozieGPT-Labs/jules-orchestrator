#!/usr/bin/env python3
"""
Tool Adapter - Makes Jules Orchestrator work across different AI coding assistants

Supports: Kilo, OpenCode, Claude Code, Cursor, Generic CLI
"""

import os
import sys
import json
import subprocess
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from pathlib import Path
from enum import Enum


class ToolType(Enum):
    """Supported AI coding tools"""

    KILO = "kilo"
    OPENCODE = "opencode"
    CLAUDE_CODE = "claude_code"
    CURSOR = "cursor"
    GENERIC = "generic"
    UNKNOWN = "unknown"


class ToolAdapter(ABC):
    """Abstract base class for tool adapters"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tool_type = ToolType.UNKNOWN

    @abstractmethod
    def detect(self) -> bool:
        """Detect if running in this tool's environment"""
        pass

    @abstractmethod
    def get_skill_path(self) -> Optional[Path]:
        """Get path where skills should be installed"""
        pass

    @abstractmethod
    def execute_command(self, command: str, args: Dict) -> Any:
        """Execute a command in this tool's context"""
        pass

    @abstractmethod
    def format_output(self, output: Any) -> str:
        """Format output for this tool"""
        pass

    @abstractmethod
    def get_context(self) -> Dict[str, Any]:
        """Get tool-specific context (repo, session, etc.)"""
        pass


class KiloAdapter(ToolAdapter):
    """Adapter for Kilo CLI"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.tool_type = ToolType.KILO

    def detect(self) -> bool:
        """Detect Kilo environment"""
        # Check for Kilo-specific env vars or config
        if os.getenv("KILO_VERSION"):
            return True
        if Path("~/.config/kilo").expanduser().exists():
            return True
        if self._is_kilo_process():
            return True
        return False

    def _is_kilo_process(self) -> bool:
        """Check if running under Kilo process"""
        try:
            parent = os.getenv("PARENT_PROCESS", "")
            return "kilo" in parent.lower()
        except:
            return False

    def get_skill_path(self) -> Optional[Path]:
        """Kilo skill path"""
        kilo_home = os.getenv("KILO_HOME", "~/.config/kilo")
        return Path(kilo_home).expanduser() / "skill" / "jules-orchestrator"

    def execute_command(self, command: str, args: Dict) -> Any:
        """Execute as Kilo command"""
        # Format as Kilo slash command
        if command == "plan_work":
            return f'/plan-work "{args.get("prompt", "")}"'
        elif command == "status":
            return "/jules-status"
        elif command == "resume":
            return "/jules-resume"
        elif command == "verify":
            return "/jules-verify"
        else:
            return f"/jules-{command}"

    def format_output(self, output: Any) -> str:
        """Format for Kilo"""
        if isinstance(output, dict):
            return json.dumps(output, indent=2)
        return str(output)

    def get_context(self) -> Dict[str, Any]:
        """Get Kilo context"""
        return {
            "tool": "kilo",
            "version": os.getenv("KILO_VERSION", "unknown"),
            "skill_path": str(self.get_skill_path()),
            "config_root": "~/.config/kilo",
        }


class OpenCodeAdapter(ToolAdapter):
    """Adapter for OpenCode"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.tool_type = ToolType.OPENCODE

    def detect(self) -> bool:
        """Detect OpenCode environment"""
        if os.getenv("OPENCODE_VERSION"):
            return True
        if Path(".opencodespace").exists():
            return True
        if self._is_opencode_process():
            return True
        return False

    def _is_opencode_process(self) -> bool:
        """Check if running under OpenCode"""
        try:
            parent = os.getenv("PARENT_PROCESS", "")
            return "opencode" in parent.lower()
        except:
            return False

    def get_skill_path(self) -> Optional[Path]:
        """OpenCode extensions path"""
        opencode_home = os.getenv("OPENCODE_HOME", "~/.opencode")
        return Path(opencode_home).expanduser() / "extensions" / "jules-orchestrator"

    def execute_command(self, command: str, args: Dict) -> Any:
        """Execute as OpenCode command"""
        # OpenCode uses different command format
        if command == "plan_work":
            prompt = args.get("prompt", "")
            return f'@jules plan-work "{prompt}"'
        elif command == "status":
            return "@jules status"
        elif command == "resume":
            return "@jules resume"
        else:
            return f"@jules {command}"

    def format_output(self, output: Any) -> str:
        """Format for OpenCode"""
        if isinstance(output, dict):
            # OpenCode prefers markdown
            return self._dict_to_markdown(output)
        return str(output)

    def _dict_to_markdown(self, data: Dict) -> str:
        """Convert dict to markdown"""
        lines = []
        for key, value in data.items():
            lines.append(f"**{key}:** {value}")
        return "\n".join(lines)

    def get_context(self) -> Dict[str, Any]:
        """Get OpenCode context"""
        return {
            "tool": "opencode",
            "version": os.getenv("OPENCODE_VERSION", "unknown"),
            "skill_path": str(self.get_skill_path()),
            "workspace": str(Path.cwd()),
        }


class ClaudeCodeAdapter(ToolAdapter):
    """Adapter for Claude Code"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.tool_type = ToolType.CLAUDE_CODE

    def detect(self) -> bool:
        """Detect Claude Code environment"""
        if os.getenv("CLAUDE_CODE_VERSION"):
            return True
        if Path(".claude").exists():
            return True
        if self._is_claude_process():
            return True
        return False

    def _is_claude_process(self) -> bool:
        """Check if running under Claude Code"""
        try:
            parent = os.getenv("PARENT_PROCESS", "")
            return "claude" in parent.lower()
        except:
            return False

    def get_skill_path(self) -> Optional[Path]:
        """Claude Code extensions path"""
        claude_home = os.getenv("CLAUDE_CODE_HOME", "~/.claude")
        return Path(claude_home).expanduser() / "skills" / "jules-orchestrator"

    def execute_command(self, command: str, args: Dict) -> Any:
        """Execute as Claude Code command"""
        # Claude Code uses natural language commands
        if command == "plan_work":
            prompt = args.get("prompt", "")
            return f'Jules: plan work for "{prompt}"'
        elif command == "status":
            return "Jules: show status"
        elif command == "resume":
            return "Jules: resume orchestration"
        else:
            return f"Jules: {command}"

    def format_output(self, output: Any) -> str:
        """Format for Claude Code"""
        if isinstance(output, dict):
            return json.dumps(output, indent=2)
        return str(output)

    def get_context(self) -> Dict[str, Any]:
        """Get Claude Code context"""
        return {
            "tool": "claude_code",
            "version": os.getenv("CLAUDE_CODE_VERSION", "unknown"),
            "skill_path": str(self.get_skill_path()),
            "project_root": str(Path.cwd()),
        }


class CursorAdapter(ToolAdapter):
    """Adapter for Cursor"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.tool_type = ToolType.CURSOR

    def detect(self) -> bool:
        """Detect Cursor environment"""
        if os.getenv("CURSOR_VERSION"):
            return True
        if Path(".cursor").exists():
            return True
        return False

    def get_skill_path(self) -> Optional[Path]:
        """Cursor extensions path"""
        cursor_home = os.getenv("CURSOR_HOME", "~/.cursor")
        return Path(cursor_home).expanduser() / "extensions" / "jules-orchestrator"

    def execute_command(self, command: str, args: Dict) -> Any:
        """Execute as Cursor command"""
        if command == "plan_work":
            return f"Cmd+Shift+P: Jules Plan Work - {args.get('prompt', '')}"
        else:
            return f"Cmd+Shift+P: Jules {command.title()}"

    def format_output(self, output: Any) -> str:
        """Format for Cursor"""
        return str(output)

    def get_context(self) -> Dict[str, Any]:
        """Get Cursor context"""
        return {
            "tool": "cursor",
            "version": os.getenv("CURSOR_VERSION", "unknown"),
            "skill_path": str(self.get_skill_path()),
        }


class GenericAdapter(ToolAdapter):
    """Generic adapter for any CLI environment"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.tool_type = ToolType.GENERIC

    def detect(self) -> bool:
        """Always works as fallback"""
        return True

    def get_skill_path(self) -> Optional[Path]:
        """Generic path"""
        home = Path.home()
        return home / ".jules-orchestrator"

    def execute_command(self, command: str, args: Dict) -> Any:
        """Execute as CLI command"""
        cli_commands = {
            "plan_work": f'jules-agent plan --prompt "{args.get("prompt", "")}"',
            "status": "jules-agent status",
            "resume": "jules-agent resume",
            "verify": "jules-agent verify",
            "start": "jules-agent start",
            "stop": "jules-agent stop",
        }
        return cli_commands.get(command, f"jules-agent {command}")

    def format_output(self, output: Any) -> str:
        """Format as plain text"""
        if isinstance(output, dict):
            return json.dumps(output, indent=2)
        return str(output)

    def get_context(self) -> Dict[str, Any]:
        """Get generic context"""
        return {
            "tool": "generic_cli",
            "skill_path": str(self.get_skill_path()),
            "cwd": str(Path.cwd()),
            "shell": os.getenv("SHELL", "unknown"),
        }


class ToolAgnosticOrchestrator:
    """
    Tool-agnostic orchestrator that works across different AI coding assistants

    Automatically detects the environment and uses the appropriate adapter
    """

    def __init__(self):
        self.adapters: List[ToolAdapter] = []
        self.current_adapter: Optional[ToolAdapter] = None
        self._register_adapters()
        self._detect_tool()

    def _register_adapters(self):
        """Register all available adapters"""
        config = self._load_config()

        self.adapters = [
            KiloAdapter(config),
            OpenCodeAdapter(config),
            ClaudeCodeAdapter(config),
            CursorAdapter(config),
            GenericAdapter(config),  # Fallback
        ]

    def _load_config(self) -> Dict:
        """Load configuration from various sources"""
        config = {}

        # Try loading from config files
        config_paths = [
            Path.home() / ".jules-orchestrator" / "config.json",
            Path.cwd() / ".jules" / "config.json",
        ]

        for path in config_paths:
            if path.exists():
                try:
                    with open(path) as f:
                        config.update(json.load(f))
                except:
                    pass

        # Environment overrides
        if os.getenv("JULES_TOOL"):
            config["force_tool"] = os.getenv("JULES_TOOL")

        return config

    def _detect_tool(self):
        """Detect which tool we're running under"""
        # Check for forced tool
        force_tool = self.config.get("force_tool")
        if force_tool:
            for adapter in self.adapters:
                if adapter.tool_type.value == force_tool:
                    self.current_adapter = adapter
                    return

        # Auto-detect
        for adapter in self.adapters:
            if adapter.detect():
                self.current_adapter = adapter
                return

        # Fallback to generic
        self.current_adapter = self.adapters[-1]

    @property
    def tool_type(self) -> ToolType:
        """Get current tool type"""
        if self.current_adapter:
            return self.current_adapter.tool_type
        return ToolType.UNKNOWN

    @property
    def skill_path(self) -> Path:
        """Get skill path for current tool"""
        if self.current_adapter:
            path = self.current_adapter.get_skill_path()
            if path:
                return path
        return Path.home() / ".jules-orchestrator"

    def execute(self, command: str, **kwargs) -> str:
        """Execute command in current tool context"""
        if not self.current_adapter:
            return "Error: No adapter available"

        result = self.current_adapter.execute_command(command, kwargs)
        return self.current_adapter.format_output(result)

    def get_install_instructions(self) -> str:
        """Get installation instructions for current tool"""
        tool = self.tool_type

        instructions = {
            ToolType.KILO: """
# Kilo Installation

1. Copy to Kilo skills directory:
   mkdir -p ~/.config/kilo/skill/jules-orchestrator
   cp -r * ~/.config/kilo/skill/jules-orchestrator/

2. Add to PATH:
   echo 'export PATH="$HOME/.config/kilo/skill/jules-orchestrator/bin:$PATH"' >> ~/.zshrc
   source ~/.zshrc

3. Use commands:
   /plan-work "Your prompt"
   /jules-status
   /jules-resume
""",
            ToolType.OPENCODE: """
# OpenCode Installation

1. Copy to OpenCode extensions:
   mkdir -p ~/.opencode/extensions/jules-orchestrator
   cp -r * ~/.opencode/extensions/jules-orchestrator/

2. Use commands:
   @jules plan-work "Your prompt"
   @jules status
   @jules resume
""",
            ToolType.CLAUDE_CODE: """
# Claude Code Installation

1. Copy to Claude skills:
   mkdir -p ~/.claude/skills/jules-orchestrator
   cp -r * ~/.claude/skills/jules-orchestrator/

2. Use commands:
   Jules: plan work for "Your prompt"
   Jules: show status
   Jules: resume orchestration
""",
            ToolType.CURSOR: """
# Cursor Installation

1. Copy to Cursor extensions:
   mkdir -p ~/.cursor/extensions/jules-orchestrator
   cp -r * ~/.cursor/extensions/jules-orchestrator/

2. Use Command Palette (Cmd+Shift+P):
   "Jules: Plan Work"
   "Jules: Show Status"
""",
            ToolType.GENERIC: """
# Generic CLI Installation

1. Install to home directory:
   ./install.sh global

2. Or manually:
   mkdir -p ~/.jules-orchestrator
   cp -r * ~/.jules-orchestrator/
   ln -s ~/.jules-orchestrator/bin/jules-agent /usr/local/bin/

3. Use commands:
   jules-agent --help
   jules-agent --repo owner/repo
""",
        }

        return instructions.get(tool, instructions[ToolType.GENERIC])

    def detect_environment(self) -> Dict[str, Any]:
        """Detect and report current environment"""
        return {
            "tool": self.tool_type.value,
            "adapter": type(self.current_adapter).__name__,
            "skill_path": str(self.skill_path),
            "context": self.current_adapter.get_context()
            if self.current_adapter
            else {},
            "is_supported": self.tool_type != ToolType.UNKNOWN,
        }


# Convenience functions for standalone usage


def get_adapter() -> ToolAgnosticOrchestrator:
    """Get the tool-agnostic orchestrator instance"""
    return ToolAgnosticOrchestrator()


def detect_and_install():
    """Detect environment and print installation instructions"""
    orchestrator = get_adapter()
    env = orchestrator.detect_environment()

    print("╔════════════════════════════════════════════════════════════╗")
    print("║     Jules Orchestrator - Environment Detection            ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    print(f"Detected Tool: {env['tool']}")
    print(f"Adapter: {env['adapter']}")
    print(f"Skill Path: {env['skill_path']}")
    print()
    print("Installation Instructions:")
    print(orchestrator.get_install_instructions())


def main():
    """CLI entry point for tool detection"""
    import argparse

    parser = argparse.ArgumentParser(description="Tool-agnostic Jules Orchestrator")
    parser.add_argument(
        "--detect", action="store_true", help="Detect environment and show instructions"
    )
    parser.add_argument(
        "--execute", type=str, help="Execute command (plan_work, status, resume)"
    )
    parser.add_argument("--prompt", type=str, help="Prompt for plan_work command")
    parser.add_argument(
        "--tool",
        type=str,
        help="Force specific tool (kilo, opencode, claude_code, cursor, generic)",
    )

    args = parser.parse_args()

    if args.tool:
        os.environ["JULES_TOOL"] = args.tool

    orchestrator = get_adapter()

    if args.detect:
        print(json.dumps(orchestrator.detect_environment(), indent=2))
    elif args.execute:
        result = orchestrator.execute(args.execute, prompt=args.prompt)
        print(result)
    else:
        detect_and_install()


if __name__ == "__main__":
    main()
