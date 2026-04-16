#!/usr/bin/env python3
"""
DependencyOptimizer - Intelligent dependency graph optimization
"""

import json
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class DependencyAnalysis:
    """Result of dependency analysis"""

    circular_deps: List[List[str]]
    redundant_deps: List[Tuple[str, str]]  # (task, redundant_dep)
    parallelizable_groups: List[List[str]]
    critical_path: List[str]
    suggested_removals: List[Tuple[str, str, str]]  # (task, dep, reason)
    suggested_additions: List[Tuple[str, str, str]]  # (task, dep, reason)


class DependencyOptimizer:
    """
    Optimizes task dependency graphs for:
    - Reducing total execution time
    - Maximizing parallelism
    - Eliminating redundant dependencies
    - Detecting circular dependencies
    """

    def __init__(self):
        self.task_graph = {}
        self.dependency_levels = {}

    def analyze(self, tasks: List[Dict]) -> DependencyAnalysis:
        """Analyze dependency graph"""
        # Build adjacency list
        graph = {}
        task_ids = {t["id"] for t in tasks}

        for task in tasks:
            task_id = task["id"]
            deps = task.get("dependencies", [])
            graph[task_id] = [d for d in deps if d in task_ids]

        # Find circular dependencies
        circular = self._find_circular_deps(graph)

        # Find redundant dependencies
        redundant = self._find_redundant_deps(graph)

        # Calculate parallelizable groups
        parallel = self._find_parallelizable_groups(graph)

        # Calculate critical path
        critical = self._find_critical_path(graph)

        # Generate suggestions
        removals = self._suggest_removals(graph)
        additions = self._suggest_additions(graph)

        return DependencyAnalysis(
            circular_deps=circular,
            redundant_deps=redundant,
            parallelizable_groups=parallel,
            critical_path=critical,
            suggested_removals=removals,
            suggested_additions=additions,
        )

    def _find_circular_deps(self, graph: Dict[str, List[str]]) -> List[List[str]]:
        """Find all circular dependencies"""
        cycles = []

        def dfs(node: str, path: List[str], visited: Set[str]):
            if node in path:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return

            if node in visited:
                return

            visited.add(node)
            path.append(node)

            for dep in graph.get(node, []):
                dfs(dep, path, visited)

            path.pop()

        for node in graph:
            dfs(node, [], set())

        return cycles

    def _find_redundant_deps(
        self, graph: Dict[str, List[str]]
    ) -> List[Tuple[str, str]]:
        """Find redundant dependencies (transitive)"""
        redundant = []

        for task_id, deps in graph.items():
            for dep in deps:
                # Check if dep is reachable through other deps
                other_deps = [d for d in deps if d != dep]
                if self._is_reachable(graph, other_deps, dep):
                    redundant.append((task_id, dep))

        return redundant

    def _is_reachable(self, graph: Dict, start_nodes: List[str], target: str) -> bool:
        """Check if target is reachable from start_nodes"""
        visited = set()
        stack = list(start_nodes)

        while stack:
            node = stack.pop()
            if node == target:
                return True
            if node in visited:
                continue
            visited.add(node)
            stack.extend(graph.get(node, []))

        return False

    def _find_parallelizable_groups(self, graph: Dict) -> List[List[str]]:
        """Find groups of tasks that can run in parallel"""
        # Use level-order grouping
        levels = []
        in_degree = {node: 0 for node in graph}

        for deps in graph.values():
            for dep in deps:
                if dep in in_degree:
                    in_degree[dep] += 1

        current_level = [n for n, d in in_degree.items() if d == 0]

        while current_level:
            levels.append(current_level)
            next_level = []

            for node in current_level:
                for dependent in self._get_dependents(graph, node):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_level.append(dependent)

            current_level = next_level

        return levels

    def _get_dependents(self, graph: Dict, node: str) -> List[str]:
        """Get all tasks that depend on node"""
        dependents = []
        for task_id, deps in graph.items():
            if node in deps:
                dependents.append(task_id)
        return dependents

    def _find_critical_path(self, graph: Dict) -> List[str]:
        """Find the critical path (longest dependency chain)"""
        memo = {}

        def longest_path(node: str) -> Tuple[int, List[str]]:
            if node in memo:
                return memo[node]

            deps = graph.get(node, [])
            if not deps:
                return 1, [node]

            max_len = 0
            max_path = []

            for dep in deps:
                length, path = longest_path(dep)
                if length > max_len:
                    max_len = length
                    max_path = path

            result = (max_len + 1, max_path + [node])
            memo[node] = result
            return result

        # Find longest path from any node
        max_length = 0
        critical_path = []

        for node in graph:
            length, path = longest_path(node)
            if length > max_length:
                max_length = length
                critical_path = path

        return critical_path

    def _suggest_removals(self, graph: Dict) -> List[Tuple[str, str, str]]:
        """Suggest dependency removals"""
        suggestions = []

        for task_id, deps in graph.items():
            for dep in deps:
                # Check if dep is already implied by other deps
                other_deps = [d for d in deps if d != dep]
                if self._is_reachable(graph, other_deps, dep):
                    suggestions.append(
                        (task_id, dep, f"Already implied through other dependencies")
                    )

        return suggestions

    def _suggest_additions(self, graph: Dict) -> List[Tuple[str, str, str]]:
        """Suggest dependency additions for safety"""
        suggestions = []

        # Suggest implicit ordering based on task types
        # This is domain-specific
        type_order = {"Config": 0, "DB": 1, "API": 2, "UI": 3, "Test": 4}

        for task_id, deps in graph.items():
            task_type = self._get_task_type(task_id)

            # Check for DB tasks that should come before API tasks
            if task_type == "API":
                for other_id in graph:
                    if other_id != task_id:
                        other_type = self._get_task_type(other_id)
                        if other_type == "DB" and other_id not in deps:
                            if not self._is_reachable(graph, deps, other_id):
                                suggestions.append(
                                    (
                                        task_id,
                                        other_id,
                                        "DB tasks should typically complete before API tasks",
                                    )
                                )

        return suggestions

    def _get_task_type(self, task_id: str) -> str:
        """Extract task type from ID (mock - would use actual task data)"""
        # This would actually look up the task
        return "unknown"

    def optimize(self, tasks: List[Dict]) -> List[Dict]:
        """Optimize task list with improved dependencies"""
        analysis = self.analyze(tasks)

        optimized = []

        for task in tasks:
            task_id = task["id"]
            deps = task.get("dependencies", [])

            # Remove redundant deps
            for t, dep in analysis.redundant_deps:
                if t == task_id and dep in deps:
                    deps = [d for d in deps if d != dep]

            # Create optimized task
            optimized_task = dict(task)
            optimized_task["dependencies"] = deps
            optimized_task["_optimization"] = {
                "redundant_deps_removed": [
                    dep for t, dep in analysis.redundant_deps if t == task_id
                ],
            }
            optimized.append(optimized_task)

        return optimized

    def estimate_execution_time(
        self, tasks: List[Dict], task_duration_estimates: Dict[str, float]
    ) -> Dict:
        """Estimate total execution time"""
        analysis = self.analyze(tasks)

        # Calculate time per level
        level_times = []
        for level in analysis.parallelizable_groups:
            level_time = max(task_duration_estimates.get(t, 300) for t in level)
            level_times.append(level_time)

        total_time = sum(level_times)
        max_parallelism = max(len(level) for level in analysis.parallelizable_groups)

        return {
            "total_estimated_seconds": total_time,
            "execution_levels": len(level_times),
            "max_parallelism": max_parallelism,
            "critical_path_length": len(analysis.critical_path),
            "parallelizable": analysis.parallelizable_groups,
        }


if __name__ == "__main__":
    # Test
    optimizer = DependencyOptimizer()

    test_tasks = [
        {"id": "T1", "type": "Config", "dependencies": []},
        {"id": "T2", "type": "DB", "dependencies": ["T1"]},
        {"id": "T3", "type": "API", "dependencies": ["T2", "T1"]},  # T1 is redundant
        {"id": "T4", "type": "UI", "dependencies": ["T3"]},
        {"id": "T5", "type": "Test", "dependencies": ["T4"]},
    ]

    analysis = optimizer.analyze(test_tasks)

    print("Dependency Analysis:")
    print(f"  Circular dependencies: {analysis.circular_deps}")
    print(f"  Redundant dependencies: {analysis.redundant_deps}")
    print(f"  Parallelizable groups: {analysis.parallelizable_groups}")
    print(f"  Critical path: {analysis.critical_path}")

    estimates = {"T1": 60, "T2": 120, "T3": 180, "T4": 240, "T5": 300}
    time_estimate = optimizer.estimate_execution_time(test_tasks, estimates)
    print(f"\nExecution time estimate: {time_estimate['total_estimated_seconds']}s")
    print(f"Max parallelism: {time_estimate['max_parallelism']}")
