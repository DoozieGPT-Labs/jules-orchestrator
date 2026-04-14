#!/usr/bin/env python3
"""
Diff Intelligence Layer - Summarize PR changes into business impact
"""

import json
import subprocess
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class FileChange:
    """Represents a file change"""

    path: str
    change_type: str  # ADDED, MODIFIED, DELETED, RENAMED
    additions: int
    deletions: int
    patch: Optional[str] = None


@dataclass
class RiskAssessment:
    """Risk level for a change"""

    level: str  # LOW, MEDIUM, HIGH, CRITICAL
    category: str
    reason: str


class DiffIntelligence:
    """
    Analyze PR diffs and generate business-level summaries
    """

    def __init__(self, repo: str):
        self.repo = repo

    def analyze_pr(self, pr_number: int, task: Optional[Dict] = None) -> Dict:
        """
        Full PR analysis
        """
        # Get PR details
        pr_details = self._get_pr_details(pr_number)

        # Get file changes
        file_changes = self._get_file_changes(pr_number)

        # Categorize changes
        categorized = self._categorize_changes(file_changes)

        # Assess risk
        risk_assessment = self._assess_risk(file_changes, task)

        # Generate summary
        summary = self._generate_summary(
            pr_details, file_changes, categorized, risk_assessment
        )

        return {
            "pr_number": pr_number,
            "title": pr_details.get("title", ""),
            "author": pr_details.get("author", {}).get("login", ""),
            "created_at": pr_details.get("createdAt", ""),
            "summary": summary,
            "file_analysis": {
                "total_files": len(file_changes),
                "added": len([f for f in file_changes if f.change_type == "ADDED"]),
                "modified": len(
                    [f for f in file_changes if f.change_type == "MODIFIED"]
                ),
                "deleted": len([f for f in file_changes if f.change_type == "DELETED"]),
                "total_additions": sum(f.additions for f in file_changes),
                "total_deletions": sum(f.deletions for f in file_changes),
            },
            "categorized": categorized,
            "risk": risk_assessment,
            "business_impact": self._assess_business_impact(file_changes, task),
            "testing_impact": self._assess_testing_impact(file_changes),
            "deployment_impact": self._assess_deployment_impact(file_changes),
        }

    def _get_pr_details(self, pr_number: int) -> Dict:
        """Get PR details from GitHub"""
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "view",
                    str(pr_number),
                    "-R",
                    self.repo,
                    "--json",
                    "number,title,author,createdAt,body,headRefName,baseRefName",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(result.stdout)
        except Exception:
            return {}

    def _get_file_changes(self, pr_number: int) -> List[FileChange]:
        """Get detailed file changes from PR"""
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "view",
                    str(pr_number),
                    "-R",
                    self.repo,
                    "--json",
                    "files",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)
            files = data.get("files", [])

            changes = []
            for f in files:
                changes.append(
                    FileChange(
                        path=f.get("path", ""),
                        change_type=f.get("changeType", "MODIFIED"),
                        additions=f.get("additions", 0),
                        deletions=f.get("deletions", 0),
                        patch=f.get("patch", ""),
                    )
                )
            return changes
        except Exception:
            return []

    def _categorize_changes(self, changes: List[FileChange]) -> Dict[str, List[str]]:
        """Categorize changes by module/type"""
        categories = {
            "Database": [],
            "API/Controllers": [],
            "UI/Views": [],
            "Models": [],
            "Tests": [],
            "Configuration": [],
            "Documentation": [],
            "Other": [],
        }

        for change in changes:
            path = change.path.lower()

            if "migration" in path or "database" in path:
                categories["Database"].append(change.path)
            elif "controller" in path or "api" in path or path.startswith("routes/"):
                categories["API/Controllers"].append(change.path)
            elif "view" in path or path.endswith(".blade.php"):
                categories["UI/Views"].append(change.path)
            elif "model" in path and not "controller" in path:
                categories["Models"].append(change.path)
            elif "test" in path or path.startswith("tests/"):
                categories["Tests"].append(change.path)
            elif (
                path.endswith(".json")
                or path.endswith(".yml")
                or path.endswith(".yaml")
            ):
                categories["Configuration"].append(change.path)
            elif path.endswith(".md"):
                categories["Documentation"].append(change.path)
            else:
                categories["Other"].append(change.path)

        # Remove empty categories
        return {k: v for k, v in categories.items() if v}

    def _assess_risk(
        self, changes: List[FileChange], task: Optional[Dict]
    ) -> RiskAssessment:
        """
        Assess risk level of changes
        """
        # Check for high-risk files
        high_risk_patterns = [
            "migration",
            "database",
            "config/app",
            "config/auth",
            "user.php",
            "auth.php",
            "middleware",
            "kernel",
        ]

        critical_patterns = [
            "composer.json",
            "package.json",
            ".env",
            "dockerfile",
            "docker-compose",
            "deployment",
        ]

        for change in changes:
            path = change.path.lower()

            # Check critical
            for pattern in critical_patterns:
                if pattern in path:
                    return RiskAssessment(
                        level="CRITICAL",
                        category="Infrastructure",
                        reason=f"Modifies critical file: {change.path}",
                    )

            # Check high risk
            for pattern in high_risk_patterns:
                if pattern in path:
                    return RiskAssessment(
                        level="HIGH",
                        category="Core System",
                        reason=f"Modifies core system: {change.path}",
                    )

        # Check database changes
        db_changes = [c for c in changes if "migration" in c.path.lower()]
        if db_changes:
            return RiskAssessment(
                level="HIGH",
                category="Database",
                reason="Database schema changes require careful review",
            )

        # Check for auth changes
        auth_changes = [c for c in changes if "auth" in c.path.lower()]
        if auth_changes:
            return RiskAssessment(
                level="HIGH",
                category="Security",
                reason="Authentication-related changes",
            )

        # Check size
        total_lines = sum(c.additions + c.deletions for c in changes)
        if total_lines > 500:
            return RiskAssessment(
                level="MEDIUM",
                category="Size",
                reason=f"Large change: {total_lines} lines",
            )

        return RiskAssessment(
            level="LOW", category="Standard", reason="Standard code changes"
        )

    def _assess_business_impact(
        self, changes: List[FileChange], task: Optional[Dict]
    ) -> Dict:
        """Assess business impact"""
        impacts = []

        # Check for feature additions
        feature_patterns = ["controller", "api", "endpoint"]
        for change in changes:
            if any(p in change.path.lower() for p in feature_patterns):
                impacts.append("New API endpoint or feature")
                break

        # Check for UI changes
        ui_changes = [
            c
            for c in changes
            if c.path.endswith(".blade.php") or "view" in c.path.lower()
        ]
        if ui_changes:
            impacts.append("User interface changes")

        # Check for model changes
        model_changes = [
            c
            for c in changes
            if "model" in c.path.lower() and "controller" not in c.path.lower()
        ]
        if model_changes:
            impacts.append("Data model changes (may affect existing data)")

        # Check test coverage
        test_changes = [c for c in changes if "test" in c.path.lower()]
        if not test_changes and len(changes) > 1:
            impacts.append("⚠️ No test changes detected")
        else:
            impacts.append("✓ Tests included")

        return {
            "description": "; ".join(impacts) if impacts else "Standard maintenance",
            "features_added": len(
                [c for c in changes if "controller" in c.path.lower()]
            ),
            "ui_modified": len(ui_changes),
            "tests_included": len(test_changes),
        }

    def _assess_testing_impact(self, changes: List[FileChange]) -> Dict:
        """Assess testing impact"""
        test_files = [c for c in changes if "test" in c.path.lower()]
        source_files = [
            c
            for c in changes
            if "test" not in c.path.lower() and c.path.endswith(".php")
        ]

        coverage = "Full" if len(test_files) >= len(source_files) else "Partial"
        if not test_files:
            coverage = "Missing"

        return {
            "test_files_added": len(test_files),
            "source_files_modified": len(source_files),
            "coverage_status": coverage,
            "recommendation": "Add tests" if not test_files else "Coverage adequate",
        }

    def _assess_deployment_impact(self, changes: List[FileChange]) -> Dict:
        """Assess deployment impact"""
        # Check for migrations
        migrations = [c for c in changes if "migration" in c.path.lower()]

        # Check for config changes
        config_changes = [
            c for c in changes if c.path.endswith(".json") or c.path.endswith(".yml")
        ]

        # Check for breaking changes
        breaking_indicators = ["deleted", "renamed", "removed"]
        has_breaking = any(
            any(ind in c.change_type.lower() for ind in breaking_indicators)
            for c in changes
        )

        steps = []
        if migrations:
            steps.append("Run migrations: `php artisan migrate`")
        if config_changes:
            steps.append("Update configuration")
        if has_breaking:
            steps.append("⚠️ Review for breaking changes")
        steps.append("Clear cache: `php artisan cache:clear`")

        return {
            "requires_migration": len(migrations) > 0,
            "config_changes": len(config_changes) > 0,
            "potential_breaking": has_breaking,
            "deployment_steps": steps,
        }

    def _generate_summary(
        self,
        pr_details: Dict,
        changes: List[FileChange],
        categorized: Dict,
        risk: RiskAssessment,
    ) -> str:
        """Generate human-readable summary"""
        lines = [
            f"## PR Summary: {pr_details.get('title', 'Unknown')}",
            "",
            f"**Author:** {pr_details.get('author', {}).get('login', 'Unknown')}",
            f"**Files Changed:** {len(changes)}",
            f"**Total Lines:** +{sum(c.additions for c in changes)} / -{sum(c.deletions for c in changes)}",
            "",
            "### Changes by Module",
        ]

        for category, files in categorized.items():
            lines.append(f"- **{category}:** {len(files)} file(s)")

        lines.extend(
            [
                "",
                f"### Risk Level: {risk.level}",
                f"- Category: {risk.category}",
                f"- Reason: {risk.reason}",
                "",
                "### Recommendations",
            ]
        )

        if risk.level == "CRITICAL":
            lines.append(
                "- ⚠️ **REQUIRES MANUAL REVIEW** - Critical infrastructure changes"
            )
        elif risk.level == "HIGH":
            lines.append("- ⚠️ Careful review required - High impact changes")
        elif risk.level == "MEDIUM":
            lines.append("- ✓ Standard review - Medium risk")
        else:
            lines.append("- ✓ Low risk - Can auto-merge after CI passes")

        if not any("test" in c.path.lower() for c in changes):
            lines.append("- ⚠️ Consider adding tests for this change")

        return "\n".join(lines)

    def generate_report(self, pr_number: int, task: Optional[Dict] = None) -> str:
        """Generate full report"""
        analysis = self.analyze_pr(pr_number, task)

        lines = [
            "═" * 70,
            "DIFF INTELLIGENCE REPORT",
            "═" * 70,
            "",
            analysis["summary"],
            "",
            "═" * 70,
            "FILE STATISTICS",
            "═" * 70,
            f"Total Files: {analysis['file_analysis']['total_files']}",
            f"  Added: {analysis['file_analysis']['added']}",
            f"  Modified: {analysis['file_analysis']['modified']}",
            f"  Deleted: {analysis['file_analysis']['deleted']}",
            f"Line Changes: +{analysis['file_analysis']['total_additions']} / -{analysis['file_analysis']['total_deletions']}",
            "",
            "═" * 70,
            "RISK ASSESSMENT",
            "═" * 70,
            f"Level: {analysis['risk'].level}",
            f"Category: {analysis['risk'].category}",
            f"Reason: {analysis['risk'].reason}",
            "",
            "═" * 70,
            "BUSINESS IMPACT",
            "═" * 70,
            analysis["business_impact"]["description"],
            f"Features Added: {analysis['business_impact']['features_added']}",
            f"UI Modified: {analysis['business_impact']['ui_modified']}",
            "",
            "═" * 70,
            "TESTING IMPACT",
            "═" * 70,
            f"Test Files: {analysis['testing_impact']['test_files_added']}",
            f"Coverage: {analysis['testing_impact']['coverage_status']}",
            f"Recommendation: {analysis['testing_impact']['recommendation']}",
            "",
            "═" * 70,
            "DEPLOYMENT IMPACT",
            "═" * 70,
        ]

        if analysis["deployment_impact"]["requires_migration"]:
            lines.append("⚠️ Database migrations required")
        if analysis["deployment_impact"]["potential_breaking"]:
            lines.append("⚠️ Potential breaking changes")

        lines.extend(
            [
                "",
                "Deployment Steps:",
            ]
        )
        for step in analysis["deployment_impact"]["deployment_steps"]:
            lines.append(f"  • {step}")

        lines.append("")
        lines.append("═" * 70)

        return "\n".join(lines)


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python diff_intelligence.py <repo> <pr_number>")
        sys.exit(1)

    repo = sys.argv[1]
    pr_number = int(sys.argv[2])

    intel = DiffIntelligence(repo)
    report = intel.generate_report(pr_number)
    print(report)
