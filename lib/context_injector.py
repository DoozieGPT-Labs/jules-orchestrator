#!/usr/bin/env python3
"""
ContextInjector - Inject context from previous successful tasks
"""

import json
import hashlib
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class TaskContext:
    """Context from a completed task"""

    task_id: str
    task_type: str
    success_patterns: List[str]
    file_patterns_created: List[str]
    common_imports: List[str]
    api_endpoints: List[str]
    database_tables: List[str]
    configuration_keys: List[str]
    error_patterns_avoided: List[str]
    quality_score: float


class ContextInjector:
    """
    Injects context from previous successful tasks into new tasks.

    Learns from successful executions to provide better guidance:
    - Common file patterns
    - Import statements
    - API patterns
    - Database patterns
    - Configuration patterns
    """

    def __init__(self, repo: str, context_dir: str = ".jules/context"):
        self.repo = repo
        self.context_dir = Path(context_dir)
        self.context_dir.mkdir(parents=True, exist_ok=True)

        self.task_contexts: Dict[str, TaskContext] = {}
        self.type_patterns: Dict[str, List[TaskContext]] = defaultdict(list)

        self._load_contexts()

    def _load_contexts(self):
        """Load existing task contexts"""
        for context_file in self.context_dir.glob("*.json"):
            try:
                with open(context_file) as f:
                    data = json.load(f)
                    context = TaskContext(**data)
                    self.task_contexts[context.task_id] = context
                    self.type_patterns[context.task_type].append(context)
            except Exception:
                pass

    def _save_context(self, context: TaskContext):
        """Save task context"""
        try:
            context_file = self.context_dir / f"{context.task_id}.json"
            with open(context_file, "w") as f:
                json.dump(context.__dict__, f, indent=2)
        except Exception:
            pass

    def extract_context_from_task(
        self, task: Dict, pr_files: List[str], pr_content: str
    ) -> TaskContext:
        """Extract context from a completed task"""

        # Analyze files
        file_patterns = self._extract_file_patterns(pr_files)
        imports = self._extract_imports(pr_content)
        apis = self._extract_api_patterns(pr_content)
        tables = self._extract_database_patterns(pr_content)
        config = self._extract_config_patterns(pr_content)

        # Success patterns
        success_patterns = self._identify_success_patterns(task, pr_files)

        # Error patterns avoided
        error_patterns = self._identify_avoided_errors(pr_content)

        context = TaskContext(
            task_id=task["id"],
            task_type=task.get("type", "unknown"),
            success_patterns=success_patterns,
            file_patterns_created=file_patterns,
            common_imports=imports,
            api_endpoints=apis,
            database_tables=tables,
            configuration_keys=config,
            error_patterns_avoided=error_patterns,
            quality_score=task.get("quality_score", 0.8),
        )

        # Save context
        self._save_context(context)
        self.task_contexts[task["id"]] = context
        self.type_patterns[task.get("type", "unknown")].append(context)

        return context

    def _extract_file_patterns(self, files: List[str]) -> List[str]:
        """Extract common file patterns"""
        patterns = []

        for f in files:
            # Pattern matching
            if "Controller" in f:
                patterns.append("Controller pattern")
            if "Model" in f:
                patterns.append("Model pattern")
            if "Test" in f:
                patterns.append("Test file pattern")
            if "migration" in f.lower():
                patterns.append("Migration pattern")
            if "config" in f.lower():
                patterns.append("Configuration file")

        return list(set(patterns))

    def _extract_imports(self, content: str) -> List[str]:
        """Extract common import statements"""
        imports = []
        lines = content.split("\n")

        for line in lines:
            line = line.strip()
            if line.startswith("import ") or line.startswith("use "):
                imports.append(line.split()[1] if len(line.split()) > 1 else line)

        return imports[:20]  # Limit to top 20

    def _extract_api_patterns(self, content: str) -> List[str]:
        """Extract API endpoint patterns"""
        apis = []

        # Look for route definitions
        if "Route::" in content or "@app.route" in content:
            apis.append("Route definitions found")

        # Look for controller methods
        if "public function" in content and "Action" in content:
            apis.append("Controller actions")

        return apis

    def _extract_database_patterns(self, content: str) -> List[str]:
        """Extract database patterns"""
        tables = []

        if "Schema::create" in content or "CREATE TABLE" in content:
            tables.append("Table creation")

        if "hasMany" in content or "belongsTo" in content:
            tables.append("Eloquent relationships")

        return tables

    def _extract_config_patterns(self, content: str) -> List[str]:
        """Extract configuration patterns"""
        config = []

        if "env(" in content or "getenv(" in content:
            config.append("Environment variables")

        if "config(" in content:
            config.append("Configuration access")

        return config

    def _identify_success_patterns(self, task: Dict, files: List[str]) -> List[str]:
        """Identify patterns that led to success"""
        patterns = []

        # Check for test files
        if any("test" in f.lower() for f in files):
            patterns.append("Included test files")

        # Check for documentation
        if any(f.endswith(".md") for f in files):
            patterns.append("Included documentation")

        # Check acceptance criteria
        criteria = task.get("acceptance_criteria", [])
        if len(criteria) >= 3:
            patterns.append("Well-defined acceptance criteria")

        return patterns

    def _identify_avoided_errors(self, content: str) -> List[str]:
        """Identify error patterns that were avoided"""
        avoided = []

        if "try" in content and "catch" in content:
            avoided.append("Proper exception handling")

        if "null" not in content.lower() or "??" in content:
            avoided.append("Null safety")

        return avoided

    def inject_context(self, task: Dict, previous_tasks: List[str]) -> str:
        """Generate context injection for a task"""
        task_type = task.get("type", "unknown")

        # Get relevant contexts
        relevant_contexts = []

        # By type
        if task_type in self.type_patterns:
            relevant_contexts.extend(self.type_patterns[task_type])

        # By dependency
        for dep_id in task.get("dependencies", []):
            if dep_id in self.task_contexts:
                relevant_contexts.append(self.task_contexts[dep_id])

        if not relevant_contexts:
            return ""

        # Aggregate patterns
        sections = []

        # File patterns
        all_patterns = set()
        for ctx in relevant_contexts:
            all_patterns.update(ctx.file_patterns_created)

        if all_patterns:
            sections.append(f"""
## Patterns from Previous Tasks
Based on previous successful tasks, consider these patterns:
""")
            for pattern in all_patterns[:5]:
                sections.append(f"- {pattern}")

        # Common imports
        all_imports = defaultdict(int)
        for ctx in relevant_contexts:
            for imp in ctx.common_imports:
                all_imports[imp] += 1

        common_imports = [imp for imp, count in all_imports.items() if count >= 2]
        if common_imports:
            sections.append(f"""

## Common Imports
Previous tasks often use these imports:
```
{chr(10).join(common_imports[:10])}
```
""")

        # API patterns
        api_patterns = set()
        for ctx in relevant_contexts:
            api_patterns.update(ctx.api_endpoints)

        if api_patterns:
            sections.append(f"""

## API Patterns
""")
            for pattern in api_patterns[:3]:
                sections.append(f"- {pattern}")

        # Database patterns
        db_patterns = set()
        for ctx in relevant_contexts:
            db_patterns.update(ctx.database_tables)

        if db_patterns:
            sections.append(f"""

## Database Patterns
""")
            for pattern in db_patterns[:3]:
                sections.append(f"- {pattern}")

        # Success factors
        success_factors = set()
        for ctx in relevant_contexts:
            success_factors.update(ctx.success_patterns)

        if success_factors:
            sections.append(f"""

## Success Factors
Tasks with these characteristics succeed more often:
""")
            for factor in success_factors[:5]:
                sections.append(f"- ✅ {factor}")

        return "\n".join(sections)

    def get_relevant_context_summary(self, task: Dict) -> Dict:
        """Get summary of relevant context for a task"""
        task_type = task.get("type", "unknown")

        contexts = self.type_patterns.get(task_type, [])

        return {
            "task_type": task_type,
            "similar_tasks_available": len(contexts),
            "avg_quality_score": sum(c.quality_score for c in contexts) / len(contexts)
            if contexts
            else 0,
            "common_patterns": self._aggregate_patterns(contexts),
        }

    def _aggregate_patterns(self, contexts: List[TaskContext]) -> Dict:
        """Aggregate patterns across contexts"""
        patterns = defaultdict(lambda: defaultdict(int))

        for ctx in contexts:
            for p in ctx.file_patterns_created:
                patterns["file_patterns"][p] += 1
            for p in ctx.success_patterns:
                patterns["success_factors"][p] += 1

        return {
            "file_patterns": dict(patterns["file_patterns"]),
            "success_factors": dict(patterns["success_factors"]),
        }


if __name__ == "__main__":
    # Test
    injector = ContextInjector("test/repo")

    # Simulate extracting context
    task = {
        "id": "T1",
        "type": "API",
        "quality_score": 0.9,
    }

    files = [
        "app/Http/Controllers/UserController.php",
        "app/Models/User.php",
        "tests/UserControllerTest.php",
    ]

    content = """
import Controller from 'app/Http/Controller';
import User from 'app/Models/User';

class UserController extends Controller {
    public function index() {
        return User::all();
    }
}
"""

    context = injector.extract_context_from_task(task, files, content)

    print("Extracted Context:")
    print(f"  File patterns: {context.file_patterns_created}")
    print(f"  Imports: {context.common_imports[:5]}")
    print(f"  Success patterns: {context.success_patterns}")

    # Test injection
    new_task = {
        "id": "T2",
        "type": "API",
        "dependencies": ["T1"],
    }

    injection = injector.inject_context(new_task, ["T1"])
    print(f"\nContext Injection for T2:\n{injection}")
