#!/usr/bin/env python3
"""
GitHub Utils - Centralized GitHub API operations with caching and rate limiting
"""

import json
import subprocess
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from functools import wraps
from pathlib import Path


class GitHubAPIError(Exception):
    """GitHub API error with rate limit info"""

    def __init__(
        self, message: str, status_code: int = None, rate_limited: bool = False
    ):
        super().__init__(message)
        self.status_code = status_code
        self.rate_limited = rate_limited


class RateLimiter:
    """
    Rate limiter for GitHub API calls
    GitHub has 5000 requests/hour for authenticated users
    """

    def __init__(self, requests_per_hour: int = 4500, burst_size: int = 100):
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size
        self.min_interval = 3600 / requests_per_hour  # seconds between requests
        self.last_request_time = 0
        self.request_count = 0
        self.hour_start = time.time()

    def wait_if_needed(self):
        """Wait if we've exceeded rate limit"""
        now = time.time()

        # Reset hourly counter
        if now - self.hour_start > 3600:
            self.request_count = 0
            self.hour_start = now

        # Check hourly limit
        if self.request_count >= self.requests_per_hour:
            sleep_time = 3600 - (now - self.hour_start) + 1
            if sleep_time > 0:
                time.sleep(sleep_time)
            self.request_count = 0
            self.hour_start = time.time()

        # Enforce minimum interval
        elapsed = now - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

        self.last_request_time = time.time()
        self.request_count += 1


class Cache:
    """Simple file-based cache for API responses"""

    def __init__(self, cache_dir: str = ".jules/cache", ttl_seconds: int = 60):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_seconds

    def _get_cache_file(self, key: str) -> Path:
        """Get cache file path for key"""
        import hashlib

        hashed = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{hashed}.json"

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired"""
        cache_file = self._get_cache_file(key)

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r") as f:
                data = json.load(f)

            if time.time() - data["cached_at"] > self.ttl:
                cache_file.unlink()
                return None

            return data["value"]
        except Exception:
            return None

    def set(self, key: str, value: Any):
        """Cache a value"""
        cache_file = self._get_cache_file(key)

        try:
            with open(cache_file, "w") as f:
                json.dump(
                    {
                        "cached_at": time.time(),
                        "value": value,
                    },
                    f,
                )
        except Exception:
            pass

    def invalidate(self, pattern: str = None):
        """Invalidate cache entries"""
        if pattern:
            for f in self.cache_dir.glob("*.json"):
                try:
                    with open(f, "r") as file:
                        data = json.load(file)
                    if pattern in str(data.get("value", "")):
                        f.unlink()
                except Exception:
                    pass
        else:
            for f in self.cache_dir.glob("*.json"):
                try:
                    f.unlink()
                except Exception:
                    pass


class GitHubClient:
    """
    Centralized GitHub API client with:
    - Rate limiting
    - Response caching
    - Error handling
    - Retry logic
    """

    def __init__(self, repo: str, cache_ttl: int = 60):
        self.repo = repo
        self.rate_limiter = RateLimiter()
        self.cache = Cache(ttl_seconds=cache_ttl)
        self.request_count = 0
        self.error_count = 0

    def _call_gh(
        self, args: List[str], use_cache: bool = False, cache_key: str = None
    ) -> Any:
        """
        Call gh CLI with rate limiting and caching
        """
        # Check cache first
        if use_cache and cache_key:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        # Rate limiting
        self.rate_limiter.wait_if_needed()

        try:
            result = subprocess.run(
                ["gh"] + args,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )

            self.request_count += 1

            # Parse JSON if possible
            try:
                value = json.loads(result.stdout)
            except json.JSONDecodeError:
                value = result.stdout.strip()

            # Cache result
            if use_cache and cache_key:
                self.cache.set(cache_key, value)

            return value

        except subprocess.CalledProcessError as e:
            self.error_count += 1

            # Check for rate limiting
            if "rate limit" in e.stderr.lower() or e.returncode == 403:
                raise GitHubAPIError(
                    f"Rate limited: {e.stderr}", status_code=403, rate_limited=True
                )

            raise GitHubAPIError(
                f"GitHub API error: {e.stderr}", status_code=e.returncode
            )
        except subprocess.TimeoutExpired:
            raise GitHubAPIError("Request timeout", status_code=408)

    # =========================================================================
    # Issue Operations
    # =========================================================================

    def list_issues(self, state: str = "open", labels: List[str] = None) -> List[Dict]:
        """List issues in repo"""
        args = [
            "issue",
            "list",
            "-R",
            self.repo,
            "--state",
            state,
            "--json",
            "number,title,state,labels",
        ]

        if labels:
            args.extend(["--label", ",".join(labels)])

        return self._call_gh(args, use_cache=True, cache_key=f"issues_{state}_{labels}")

    def get_issue(self, issue_number: int) -> Optional[Dict]:
        """Get issue details"""
        try:
            return self._call_gh(
                [
                    "issue",
                    "view",
                    str(issue_number),
                    "-R",
                    self.repo,
                    "--json",
                    "number,title,state,body,labels",
                ],
                use_cache=True,
                cache_key=f"issue_{issue_number}",
            )
        except GitHubAPIError:
            return None

    def create_issue(
        self, title: str, body: str, labels: List[str] = None
    ) -> Optional[int]:
        """Create issue and return number"""
        args = [
            "issue",
            "create",
            "-R",
            self.repo,
            "--title",
            title,
            "--body",
            body,
        ]

        if labels:
            args.extend(["--label", ",".join(labels)])

        try:
            result = self._call_gh(args, use_cache=False)
            # Parse issue number from URL
            if isinstance(result, str):
                return int(result.split("/")[-1])
            return None
        except GitHubAPIError:
            return None

    def close_issue(self, issue_number: int) -> bool:
        """Close an issue"""
        try:
            self._call_gh(
                ["issue", "close", str(issue_number), "-R", self.repo], use_cache=False
            )
            self.cache.invalidate(f"issue_{issue_number}")
            return True
        except GitHubAPIError:
            return False

    def add_comment(self, issue_number: int, body: str) -> bool:
        """Add comment to issue"""
        try:
            self._call_gh(
                [
                    "issue",
                    "comment",
                    str(issue_number),
                    "-R",
                    self.repo,
                    "--body",
                    body,
                ],
                use_cache=False,
            )
            return True
        except GitHubAPIError:
            return False

    # =========================================================================
    # PR Operations
    # =========================================================================

    def list_prs(self, state: str = "open") -> List[Dict]:
        """List PRs"""
        return self._call_gh(
            [
                "pr",
                "list",
                "-R",
                self.repo,
                "--state",
                state,
                "--json",
                "number,title,state,headRefName,baseRefName,merged",
            ],
            use_cache=True,
            cache_key=f"prs_{state}",
        )

    def get_pr(self, pr_number: int) -> Optional[Dict]:
        """Get PR details"""
        try:
            return self._call_gh(
                [
                    "pr",
                    "view",
                    str(pr_number),
                    "-R",
                    self.repo,
                    "--json",
                    "number,title,state,body,headRefName,baseRefName,merged,reviewDecision,statusCheckRollup,author",
                ],
                use_cache=True,
                cache_key=f"pr_{pr_number}",
            )
        except GitHubAPIError:
            return None

    def get_pr_files(self, pr_number: int) -> List[str]:
        """Get files changed in PR"""
        result = self._call_gh(
            ["pr", "view", str(pr_number), "-R", self.repo, "--json", "files"],
            use_cache=True,
            cache_key=f"pr_files_{pr_number}",
        )
        return [f.get("path", "") for f in result.get("files", [])]

    def create_pr(self, title: str, body: str, head: str, base: str) -> Optional[int]:
        """Create PR and return number"""
        try:
            result = self._call_gh(
                [
                    "pr",
                    "create",
                    "-R",
                    self.repo,
                    "--title",
                    title,
                    "--body",
                    body,
                    "--head",
                    head,
                    "--base",
                    base,
                ],
                use_cache=False,
            )
            if isinstance(result, str):
                return int(result.split("/")[-1])
            return None
        except GitHubAPIError:
            return None

    def approve_pr(self, pr_number: int, body: str = "Auto-approved") -> bool:
        """Approve PR"""
        try:
            self._call_gh(
                [
                    "pr",
                    "review",
                    str(pr_number),
                    "-R",
                    self.repo,
                    "--approve",
                    "--body",
                    body,
                ],
                use_cache=False,
            )
            self.cache.invalidate(f"pr_{pr_number}")
            return True
        except GitHubAPIError:
            return False

    def merge_pr(
        self, pr_number: int, squash: bool = True, delete_branch: bool = True
    ) -> bool:
        """Merge PR"""
        args = ["pr", "merge", str(pr_number), "-R", self.repo]

        if squash:
            args.append("--squash")
        if delete_branch:
            args.append("--delete-branch")

        try:
            self._call_gh(args, use_cache=False)
            self.cache.invalidate(f"pr_{pr_number}")
            return True
        except GitHubAPIError:
            return False

    def is_pr_approved(self, pr_number: int) -> bool:
        """Check if PR is approved"""
        pr = self.get_pr(pr_number)
        return pr.get("reviewDecision") == "APPROVED" if pr else False

    def is_pr_merged(self, pr_number: int) -> bool:
        """Check if PR is merged"""
        pr = self.get_pr(pr_number)
        return pr.get("merged") or pr.get("state") == "MERGED" if pr else False

    def check_ci_status(self, pr_number: int) -> bool:
        """Check CI status"""
        pr = self.get_pr(pr_number)
        if not pr:
            return False

        checks = pr.get("statusCheckRollup", [])
        if not checks:
            return True  # No CI configured

        return all(
            c.get("state") == "SUCCESS" or c.get("conclusion") == "SUCCESS"
            for c in checks
        )

    # =========================================================================
    # Repo Operations
    # =========================================================================

    def get_repo_info(self) -> Optional[Dict]:
        """Get repository info"""
        try:
            return self._call_gh(
                ["repo", "view", self.repo, "--json", "name,owner,defaultBranch"],
                use_cache=True,
                cache_key="repo_info",
            )
        except GitHubAPIError:
            return None

    def create_branch(self, branch_name: str, base: str = "main") -> bool:
        """Create branch"""
        try:
            self._call_gh(
                [
                    "api",
                    "-X",
                    "POST",
                    f"repos/{self.repo}/git/refs",
                    "-f",
                    f"ref=refs/heads/{branch_name}",
                    "-f",
                    f"sha=$(gh api repos/{self.repo}/git/ref/heads/{base} --jq .object.sha)",
                ],
                use_cache=False,
            )
            return True
        except GitHubAPIError:
            return False

    def get_file_content(self, path: str, ref: str = "HEAD") -> Optional[str]:
        """Get file content from repo"""
        try:
            result = self._call_gh(
                ["api", f"repos/{self.repo}/contents/{path}?ref={ref}"],
                use_cache=True,
                cache_key=f"file_{path}_{ref}",
            )

            import base64

            if isinstance(result, dict) and "content" in result:
                return base64.b64decode(result["content"]).decode("utf-8")
            return None
        except GitHubAPIError:
            return None

    # =========================================================================
    # Stats
    # =========================================================================

    def get_stats(self) -> Dict:
        """Get client statistics"""
        return {
            "requests": self.request_count,
            "errors": self.error_count,
            "error_rate": self.error_count / max(self.request_count, 1),
            "cache_size": len(list(self.cache.cache_dir.glob("*.json"))),
        }

    def clear_cache(self):
        """Clear all cached data"""
        self.cache.invalidate()


def with_retry(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator for retry logic"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except GitHubAPIError as e:
                    last_exception = e

                    # Don't retry on rate limit
                    if e.rate_limited:
                        raise

                    if attempt < max_retries:
                        time.sleep(current_delay)
                        current_delay *= backoff
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        time.sleep(current_delay)
                        current_delay *= backoff

            raise last_exception

        return wrapper

    return decorator


# Convenience functions for common operations


def find_pr_by_task_id(
    client: GitHubClient, task_id: str, issue_id: Optional[int] = None
) -> Optional[Dict]:
    """Find PR associated with a task"""
    # Check open PRs first
    for state in ["open", "merged"]:
        prs = client.list_prs(state=state)
        for pr in prs:
            pr_title = pr.get("title", "")
            pr_body = pr.get("body", "")
            branch = pr.get("headRefName", "")

            # Match by task ID in title
            if task_id in pr_title:
                return pr

            # Match by issue reference in body
            if issue_id and f"#{issue_id}" in pr_body:
                return pr

            # Match by branch name
            if task_id.lower() in branch.lower():
                return pr

    return None


def check_issue_exists(client: GitHubClient, title_pattern: str) -> Optional[int]:
    """Check if issue with pattern already exists"""
    issues = client.list_issues(state="all")
    for issue in issues:
        if title_pattern in issue.get("title", ""):
            return issue["number"]
    return None


if __name__ == "__main__":
    # Test
    import sys

    if len(sys.argv) < 2:
        print("Usage: python github_utils.py <repo>")
        sys.exit(1)

    repo = sys.argv[1]
    client = GitHubClient(repo)

    print(f"Testing GitHub client for {repo}...")

    # Test repo info
    info = client.get_repo_info()
    print(f"Repo info: {info}")

    # Test PR list
    prs = client.list_prs()
    print(f"Found {len(prs)} open PRs")

    # Stats
    print(f"Stats: {client.get_stats()}")
