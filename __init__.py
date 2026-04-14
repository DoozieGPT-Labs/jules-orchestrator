"""
Jules Orchestrator v3.0
Async AI software factory with background tracking and auto-approval
"""

__version__ = "3.0.0"
__author__ = "Claude Code Team"

from .background_agent import JulesBackgroundAgent
from .dependency_resolver import DependencyResolver
from .resume_logic import JulesResumeLogic

__all__ = ["JulesBackgroundAgent", "DependencyResolver", "JulesResumeLogic"]
