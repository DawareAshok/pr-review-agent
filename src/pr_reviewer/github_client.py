import os
import re
from typing import Any, Dict, List, Optional, Tuple
import httpx

from pr_reviewer.models import ReviewReport, ReviewVerdict
from pr_reviewer.sanitizer import validate_repo_identifier


class GitHubClientError(Exception):
    pass


def parse_pr_identifier(identifier: str) -> Tuple[str, int]:
    """
    Parses a GitHub PR identifier in various formats:
    - https://github.com/owner/repo/pull/123
    - https://github.com/owner/repo/pull/123/files
    - owner/repo#123
    - owner/repo/123
    - owner/repo 123
    Returns: (repo_full_name, pr_number)
    """
    cleaned = identifier.strip()

    # URL match
    url_pattern = r"^https?://github\.com/([^/]+/[^/]+)/pull/(\d+)(?:/.*)?$"
    match = re.match(url_pattern, cleaned)
    if match:
        repo = validate_repo_identifier(match.group(1))
        pr_num = int(match.group(2))
        if pr_num <= 0:
            raise ValueError(f"Invalid PR number: {pr_num}. Must be a positive integer.")
        return repo, pr_num

    # owner/repo#123
    hash_pattern = r"^([^/]+/[^#\s]+)#(\d+)$"
    match = re.match(hash_pattern, cleaned)
    if match:
        repo = validate_repo_identifier(match.group(1))
        pr_num = int(match.group(2))
        if pr_num <= 0:
            raise ValueError(f"Invalid PR number: {pr_num}. Must be a positive integer.")
        return repo, pr_num

    # owner/repo/123
    slash_pattern = r"^([^/]+/[^/\s]+)/(\d+)$"
    match = re.match(slash_pattern, cleaned)
    if match:
        repo = validate_repo_identifier(match.group(1))
        pr_num = int(match.group(2))
        if pr_num <= 0:
            raise ValueError(f"Invalid PR number: {pr_num}. Must be a positive integer.")
        return repo, pr_num

    # owner/repo 123
    space_pattern = r"^([^/\s]+/[^\s]+)\s+(\d+)$"
    match = re.match(space_pattern, cleaned)
    if match:
        repo = validate_repo_identifier(match.group(1))
        pr_num = int(match.group(2))
        if pr_num <= 0:
            raise ValueError(f"Invalid PR number: {pr_num}. Must be a positive integer.")
        return repo, pr_num

    raise ValueError(
        f"Invalid GitHub PR identifier '{identifier}'. "
        "Expected format: 'owner/repo#123' or 'https://github.com/owner/repo/pull/123'"
    )


class GitHubClient:
    """Client for GitHub REST API using httpx."""

    def __init__(self, token: Optional[str] = None, timeout: float = 60.0):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"
        self.timeout = timeout

    def _get_headers(self, accept: str = "application/vnd.github.v3+json") -> Dict[str, str]:
        headers = {
            "Accept": accept,
            "User-Agent": "PR-Review-Agent/0.1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get_pr_details(self, repo: str, pr_number: int) -> Dict[str, Any]:
        """Fetches metadata for a given PR."""
        repo = validate_repo_identifier(repo)
        url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, headers=self._get_headers())
            if response.status_code == 404:
                raise GitHubClientError(f"PR #{pr_number} in repo '{repo}' not found. Check repository name and permissions.")
            elif response.status_code in (401, 403):
                try:
                    msg = response.json().get("message", response.text)
                except Exception:
                    msg = response.text
                raise GitHubClientError(f"Authentication/Rate limit failed ({response.status_code}): {msg}")
            response.raise_for_status()
            return response.json()

    def get_pr_diff(self, repo: str, pr_number: int) -> str:
        """Fetches the unified git diff for a PR."""
        repo = validate_repo_identifier(repo)
        url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}"
        headers = self._get_headers(accept="application/vnd.github.v3.diff")
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, headers=headers)
            if response.status_code != 200:
                raise GitHubClientError(
                    f"Failed to fetch PR diff ({response.status_code}): {response.text}"
                )
            return response.text

    def post_issue_comment(self, repo: str, pr_number: int, comment_body: str) -> Dict[str, Any]:
        """Posts a general comment to the PR issue thread."""
        repo = validate_repo_identifier(repo)
        if not self.token:
            raise GitHubClientError("GITHUB_TOKEN is required to post comments to GitHub.")

        url = f"{self.base_url}/repos/{repo}/issues/{pr_number}/comments"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=self._get_headers(), json={"body": comment_body})
            response.raise_for_status()
            return response.json()

    def post_pull_request_review(
        self,
        repo: str,
        pr_number: int,
        commit_id: str,
        event: str,
        body: str,
        comments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Creates a formal Pull Request Review.
        event: 'APPROVE', 'REQUEST_CHANGES', or 'COMMENT'
        """
        repo = validate_repo_identifier(repo)
        if not self.token:
            raise GitHubClientError("GITHUB_TOKEN is required to post formal reviews.")

        # Normalize event (e.g. APPROVED -> APPROVE)
        if event == "APPROVED" or event == ReviewVerdict.APPROVED.value:
            event = "APPROVE"
        elif event not in ("APPROVE", "REQUEST_CHANGES", "COMMENT"):
            event = "COMMENT"

        url = f"{self.base_url}/repos/{repo}/pulls/{pr_number}/reviews"
        payload: Dict[str, Any] = {
            "commit_id": commit_id,
            "body": body,
            "event": event,
        }
        if comments:
            payload["comments"] = comments

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=self._get_headers(), json=payload)
            if response.status_code == 422 and comments:
                # If GitHub rejected inline comments (e.g., line outside diff hunk), retry with body only
                payload.pop("comments")
                response = client.post(url, headers=self._get_headers(), json=payload)
            response.raise_for_status()
            return response.json()
