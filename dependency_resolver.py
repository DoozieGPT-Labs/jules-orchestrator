#!/usr/bin/env python3
"""
Dependency Resolver - Build execution graph and resolve dependencies
"""

from typing import Dict, List, Set, Optional
from collections import defaultdict


class DependencyResolver:
    """
    Resolve task dependencies into execution levels for parallel processing
    """

    def __init__(self, tasks: List[Dict]):
        self.tasks = {t["id"]: t for t in tasks}
        self.graph = self._build_graph()

    def _build_graph(self) -> Dict[str, List[str]]:
        """Build dependency adjacency list"""
        graph = defaultdict(list)
        for task_id, task in self.tasks.items():
            deps = task.get("dependencies", [])
            graph[task_id] = deps
        return dict(graph)

    def topological_sort_levels(self) -> List[List[str]]:
        """
        Return tasks grouped by execution level using Kahn's algorithm
        Level 0: No dependencies
        Level 1: Depends only on level 0
        etc.
        """
        # Calculate in-degrees
        in_degree = {t: 0 for t in self.tasks}
        dependents = defaultdict(list)

        for task_id, deps in self.graph.items():
            for dep in deps:
                if dep in self.tasks:  # Only count valid dependencies
                    dependents[dep].append(task_id)
                    in_degree[task_id] += 1

        # Kahn's algorithm
        levels = []
        current_level = [t for t in self.tasks if in_degree[t] == 0]
        processed = set()

        while current_level:
            levels.append(current_level)
            next_level = []

            for task_id in current_level:
                processed.add(task_id)
                for dependent in dependents[task_id]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0 and dependent not in processed:
                        next_level.append(dependent)

            current_level = next_level

        # Check for cycles
        if len(processed) != len(self.tasks):
            unprocessed = set(self.tasks.keys()) - processed
            raise ValueError(f"Circular dependency detected: {unprocessed}")

        return levels

    def get_ready_tasks(self, completed_ids: Set[str]) -> List[Dict]:
        """Get tasks ready to execute (all deps complete)"""
        ready = []
        for task_id, task in self.tasks.items():
            if task.get("status") == "complete" or task_id in completed_ids:
                continue

            deps = task.get("dependencies", [])
            if all(d in completed_ids for d in deps):
                ready.append(task)

        return ready

    def get_task_depth(self, task_id: str) -> int:
        """Get the depth of a task in the dependency tree"""
        if task_id not in self.tasks:
            return -1

        visited = set()

        def calculate_depth(tid: str, visited: Set[str]) -> int:
            if tid in visited:
                return 0  # Cycle detected

            visited.add(tid)
            deps = self.graph.get(tid, [])

            if not deps:
                return 0

            max_dep_depth = 0
            for dep in deps:
                if dep in self.tasks:
                    dep_depth = calculate_depth(dep, visited.copy())
                    max_dep_depth = max(max_dep_depth, dep_depth + 1)

            return max_dep_depth

        return calculate_depth(task_id, set())

    def has_circular_dependency(self) -> bool:
        """Check for circular dependencies using DFS"""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {t: WHITE for t in self.tasks}

        def dfs(node: str) -> bool:
            color[node] = GRAY

            for neighbor in self.graph.get(node, []):
                if neighbor not in self.tasks:
                    continue

                if color[neighbor] == GRAY:
                    return True  # Back edge found

                if color[neighbor] == WHITE and dfs(neighbor):
                    return True

            color[node] = BLACK
            return False

        for node in self.tasks:
            if color[node] == WHITE:
                if dfs(node):
                    return True

        return False

    def get_dependency_chain(self, task_id: str) -> List[str]:
        """Get the full dependency chain for a task"""
        if task_id not in self.tasks:
            return []

        chain = []
        visited = set()

        def build_chain(tid: str):
            if tid in visited or tid not in self.tasks:
                return
            visited.add(tid)

            for dep in self.graph.get(tid, []):
                build_chain(dep)

            chain.append(tid)

        build_chain(task_id)
        return chain[:-1]  # Exclude the task itself

    def get_dependents(self, task_id: str) -> List[str]:
        """Get all tasks that depend on this task"""
        dependents = []
        for tid, task in self.tasks.items():
            deps = task.get("dependencies", [])
            if task_id in deps:
                dependents.append(tid)
        return dependents

    def can_execute(self, task_id: str, completed_ids: Set[str]) -> bool:
        """Check if a task can be executed (all deps complete)"""
        if task_id not in self.tasks:
            return False

        deps = self.graph.get(task_id, [])
        return all(d in completed_ids for d in deps)

    def get_parallel_groups(self) -> List[List[Dict]]:
        """Get tasks grouped by execution level with full task objects"""
        levels = self.topological_sort_levels()
        return [[self.tasks[tid] for tid in level] for level in levels]

    def validate_dependencies(self) -> List[str]:
        """Validate all dependencies exist and there are no cycles"""
        errors = []

        # Check for missing dependencies
        for task_id, deps in self.graph.items():
            for dep in deps:
                if dep not in self.tasks:
                    errors.append(f"Task {task_id}: Dependency {dep} not found")

        # Check for self-dependency
        for task_id, deps in self.graph.items():
            if task_id in deps:
                errors.append(f"Task {task_id}: Self-dependency not allowed")

        # Check for cycles
        if self.has_circular_dependency():
            errors.append("Circular dependency detected in task graph")

        return errors


def create_execution_plan(tasks: List[Dict]) -> Dict:
    """
    Create execution plan with dependency levels
    """
    resolver = DependencyResolver(tasks)

    # Validate
    errors = resolver.validate_dependencies()
    if errors:
        return {"valid": False, "errors": errors, "levels": [], "parallel_groups": []}

    # Build levels
    levels = resolver.topological_sort_levels()
    parallel_groups = resolver.get_parallel_groups()

    return {
        "valid": True,
        "errors": [],
        "levels": levels,
        "level_count": len(levels),
        "parallel_groups": parallel_groups,
        "max_parallel": max(len(level) for level in levels) if levels else 0,
    }


if __name__ == "__main__":
    # Test
    tasks = [
        {"id": "T1", "dependencies": []},
        {"id": "T2", "dependencies": []},
        {"id": "T3", "dependencies": ["T1", "T2"]},
        {"id": "T4", "dependencies": ["T1"]},
        {"id": "T5", "dependencies": ["T3", "T4"]},
        {"id": "T6", "dependencies": ["T3"]},
    ]

    resolver = DependencyResolver(tasks)
    levels = resolver.topological_sort_levels()

    print("Execution Levels:")
    for i, level in enumerate(levels):
        print(f"  Level {i}: {level}")

    print(f"\nCan execute T3 with T1 complete: {resolver.can_execute('T3', {'T1'})}")
    print(
        f"Can execute T3 with T1,T2 complete: {resolver.can_execute('T3', {'T1', 'T2'})}"
    )
