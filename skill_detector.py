#!/usr/bin/env python3
"""
Skill Detector - Auto-detect and inject skills into Jules execution
"""

import json
import fnmatch
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Union


class SkillDetector:
    """
    Detect skills based on:
    1. Repo context (package.json, composer.json, etc.)
    2. Task type (DB, API, UI, Test)
    3. File patterns
    4. User overrides
    """

    def __init__(self, skills_dir: Optional[str] = None):
        if skills_dir is None:
            # Get skill directory relative to this file
            self.skills_dir = Path(__file__).parent / "skills"
        else:
            self.skills_dir = Path(skills_dir)

        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict:
        """Load skills metadata"""
        metadata_file = self.skills_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, "r") as f:
                return json.load(f)
        return {"skills": [], "rules": {}}

    def detect_repo_type(self, repo_path: Union[str, Path] = ".") -> Dict[str, bool]:
        """Detect project type from repo files"""
        repo_path = Path(repo_path)
        detected: Dict[str, bool] = {}

        # PHP/Laravel
        if (repo_path / "composer.json").exists():
            detected["php"] = True
            detected["laravel"] = self._is_laravel(repo_path)

        # Node.js
        if (repo_path / "package.json").exists():
            detected["nodejs"] = True
            detected["react"] = self._has_react(repo_path)
            detected["vue"] = self._has_vue(repo_path)

        # Python
        if (repo_path / "requirements.txt").exists() or (
            repo_path / "pyproject.toml"
        ).exists():
            detected["python"] = True

        # Go
        if (repo_path / "go.mod").exists():
            detected["go"] = True

        # Rust
        if (repo_path / "Cargo.toml").exists():
            detected["rust"] = True

        return detected

    def _is_laravel(self, repo_path: Path) -> bool:
        """Check if Laravel project"""
        composer = repo_path / "composer.json"
        if composer.exists():
            try:
                with open(composer, "r") as f:
                    data = json.load(f)
                    deps = data.get("require", {})
                    return "laravel/framework" in deps
            except Exception:
                return False
        return False

    def _has_react(self, repo_path: Path) -> bool:
        """Check if React project"""
        pkg = repo_path / "package.json"
        if pkg.exists():
            try:
                with open(pkg, "r") as f:
                    data = json.load(f)
                    deps = {
                        **data.get("dependencies", {}),
                        **data.get("devDependencies", {}),
                    }
                    return "react" in deps
            except Exception:
                return False
        return False

    def _has_vue(self, repo_path: Path) -> bool:
        """Check if Vue project"""
        pkg = repo_path / "package.json"
        if pkg.exists():
            try:
                with open(pkg, "r") as f:
                    data = json.load(f)
                    deps = {
                        **data.get("dependencies", {}),
                        **data.get("devDependencies", {}),
                    }
                    return "vue" in deps
            except Exception:
                return False
        return False

    def detect_from_task(self, task: Dict) -> List[str]:
        """Detect skills based on task"""
        task_type = task.get("type", "")
        files = task.get("files_expected", [])

        matched_skills: List[str] = []

        for skill in self.metadata.get("skills", []):
            if not skill.get("enabled", True):
                continue

            # Check task type match
            if task_type in skill.get("applies_to", []):
                matched_skills.append(skill["name"])
                continue

            # Check file pattern match
            triggers = skill.get("triggers", [])
            for file in files:
                for trigger in triggers:
                    if self._matches_trigger(file, trigger):
                        matched_skills.append(skill["name"])
                        break

        return matched_skills

    def _matches_trigger(self, file: str, trigger: str) -> bool:
        """Check if file matches trigger pattern"""
        # Exact match
        if trigger == file:
            return True

        # Glob pattern
        if fnmatch.fnmatch(file, trigger):
            return True

        # Contains
        if trigger in file:
            return True

        return False

    def get_skills_for_task(
        self,
        task: Dict,
        repo_path: Union[str, Path] = ".",
        user_skills: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Get applicable skills for a task"""
        detected: List[str] = []

        # 1. Auto-detect from repo
        repo_type = self.detect_repo_type(repo_path)

        # 2. Auto-detect from task
        task_skills = self.detect_from_task(task)
        detected.extend(task_skills)

        # 3. Add repo-specific skills
        if repo_type.get("laravel"):
            detected.extend(["backend-api", "db-design"])

        # 4. Add user overrides
        if user_skills:
            detected.extend(user_skills)

        # Remove duplicates
        detected = list(set(detected))

        # Get full skill objects
        skills: List[Dict] = []
        for skill_name in detected:
            skill = self._get_skill(skill_name)
            if skill:
                skills.append(skill)

        # Resolve dependencies
        skills = self._resolve_dependencies(skills)

        # Sort by priority (highest first)
        skills.sort(key=lambda s: s.get("priority", 0), reverse=True)

        # Limit to max 5 skills
        max_skills = self.metadata.get("rules", {}).get("max_skills_per_task", 5)
        return skills[:max_skills]

    def _get_skill(self, name: str) -> Optional[Dict]:
        """Get skill by name"""
        for skill in self.metadata.get("skills", []):
            if skill["name"] == name:
                return skill
        return None

    def _resolve_dependencies(self, skills: List[Dict]) -> List[Dict]:
        """Resolve skill dependencies"""
        resolved: List[Dict] = []
        resolved_names: Set[str] = set()

        def add_skill(skill: Dict):
            if skill["name"] in resolved_names:
                return

            # Add dependencies first
            for dep_name in skill.get("dependencies", []):
                dep_skill = self._get_skill(dep_name)
                if dep_skill:
                    add_skill(dep_skill)

            # Add this skill
            if skill["name"] not in resolved_names:
                resolved.append(skill)
                resolved_names.add(skill["name"])

        for skill in skills:
            add_skill(skill)

        return resolved

    def load_skill_content(self, skill_name: str) -> Dict[str, str]:
        """Load all content files for a skill"""
        skill_dir = self.skills_dir / skill_name
        content: Dict[str, str] = {}

        if not skill_dir.exists():
            return content

        files = ["rules.md", "patterns.md", "anti-patterns.md"]
        for filename in files:
            filepath = skill_dir / filename
            if filepath.exists():
                with open(filepath, "r") as f:
                    content[filename.replace(".md", "")] = f.read()

        return content

    def generate_skill_prompt(self, skills: List[Dict]) -> str:
        """Generate the skill injection section for Jules prompt"""
        if not skills:
            return ""

        sections: List[str] = []
        sections.append("═" * 60)
        sections.append("APPLIED SKILLS (STRICT ENFORCEMENT)")
        sections.append("═" * 60)
        sections.append("")

        for skill in skills:
            name = skill["name"]
            content = self.load_skill_content(name)

            sections.append(f"\n[Skill: {name}]")
            sections.append(f"Priority: {skill.get('priority', 0)}")

            if "rules" in content:
                sections.append("\nRules:")
                sections.append(content["rules"][:1500])

            if "anti-patterns" in content:
                sections.append("\nAnti-Patterns (NEVER DO):")
                sections.append(content["anti-patterns"][:500])

        sections.append("\n" + "═" * 60)
        sections.append("SKILL CONSTRAINTS:")
        sections.append("You MUST follow the above skills strictly.")
        sections.append("Do not ignore them. Validate your code against these rules.")
        sections.append("═" * 60)

        return "\n".join(sections)

    def install_skills_to_project(
        self, repo_path: Union[str, Path], skills: List[str]
    ) -> bool:
        """Install skills to .jules/skills/ in the project"""
        import shutil

        jules_dir = Path(repo_path) / ".jules" / "skills"
        jules_dir.mkdir(parents=True, exist_ok=True)

        installed: List[str] = []
        for skill_name in skills:
            src_dir = self.skills_dir / skill_name
            if src_dir.exists():
                dst_dir = jules_dir / skill_name
                if dst_dir.exists():
                    shutil.rmtree(dst_dir)
                shutil.copytree(src_dir, dst_dir)
                installed.append(skill_name)

        # Create installed-skills.json
        with open(jules_dir / "installed-skills.json", "w") as f:
            json.dump(
                {"installed": installed, "timestamp": datetime.now().isoformat()},
                f,
                indent=2,
            )

        return True


# Convenience function for CLI usage
def detect_and_inject_skills(
    task: Dict,
    repo_path: Union[str, Path] = ".",
    user_skills: Optional[List[str]] = None,
) -> str:
    """One-liner to detect skills and generate prompt"""
    detector = SkillDetector()
    skills = detector.get_skills_for_task(task, repo_path, user_skills)
    return detector.generate_skill_prompt(skills)


if __name__ == "__main__":
    # Test
    detector = SkillDetector()

    test_task = {
        "id": "T2",
        "type": "API",
        "files_expected": ["app/Http/Controllers/Api/InvoiceController.php"],
    }

    skills = detector.get_skills_for_task(
        test_task, "/Users/akshaydoozie/Documents/doozie/jules-invoice-demo"
    )
    print(f"Detected skills: {[s['name'] for s in skills]}")

    prompt = detector.generate_skill_prompt(skills)
    print("\n" + "=" * 60)
    print(prompt[:2000])
