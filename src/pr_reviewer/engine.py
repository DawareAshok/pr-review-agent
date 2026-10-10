import os
from typing import Optional
from dotenv import load_dotenv

from pr_reviewer.diff_parser import parse_unified_diff
from pr_reviewer.formatter import format_markdown_report
from pr_reviewer.git_local import get_diff_from_file, get_local_diff, get_local_git_context
from pr_reviewer.github_client import GitHubClient, parse_pr_identifier
from pr_reviewer.models import ReviewReport
from pr_reviewer.prompts import DEFAULT_SYSTEM_INSTRUCTION
from pr_reviewer.providers import BaseLLMProvider, get_provider


class ReviewEngine:
    """Core review engine orchestrating diff extraction, LLM analysis, and reporting."""

    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
        github_token: Optional[str] = None,
        annotated_diff: bool = True,
        system_instruction: Optional[str] = None,
    ):
        load_dotenv()

        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        self.github_client = GitHubClient(token=self.github_token)
        self.annotated_diff = annotated_diff
        self.system_instruction = system_instruction or DEFAULT_SYSTEM_INSTRUCTION

        # Resolve provider
        if provider:
            self.provider = provider
        else:
            resolved_p_name = provider_name or os.environ.get("DEFAULT_PROVIDER", "openai")
            resolved_m_name = model_name or os.environ.get(
                "DEFAULT_MODEL", "gpt-4o-mini" if resolved_p_name.lower() in ("openai", "gpt") else None
            )
            self.provider = get_provider(provider_name=resolved_p_name, model_name=resolved_m_name)

    def review_github_pr(
        self,
        pr_target: str,
        post_review: bool = False,
        post_comment: bool = False,
    ) -> ReviewReport:
        """Fetches and reviews a remote GitHub Pull Request."""
        repo, pr_number = parse_pr_identifier(pr_target)

        # 1. Fetch metadata & diff
        pr_details = self.github_client.get_pr_details(repo, pr_number)
        raw_diff = self.github_client.get_pr_diff(repo, pr_number)

        parsed_diff = parse_unified_diff(raw_diff)
        if not parsed_diff.active_files:
            raise ValueError(f"No reviewable file changes found in PR #{pr_number} ({repo}).")

        # 2. Build formatted diff & context
        diff_text = f"<untrusted_pr_diff>\n{parsed_diff.to_review_text(annotated=self.annotated_diff)}\n</untrusted_pr_diff>"
        pr_context = f"""<untrusted_pr_context>
Repository: {repo}
PR #{pr_number}: {pr_details.get('title', 'No Title')}
Author: @{pr_details.get('user', {}).get('login', 'unknown')}
Branches: {pr_details.get('head', {}).get('ref')} -> {pr_details.get('base', {}).get('ref')}
Description:
{pr_details.get('body') or 'No description provided.'}
</untrusted_pr_context>"""

        # 3. Invoke LLM review
        report = self.provider.review_diff(
            diff_text=diff_text,
            pr_context=pr_context,
            system_instruction=self.system_instruction,
        )

        # 4. Fill diff metadata
        report.pr_identifier = f"{repo}#{pr_number}"
        report.files_analyzed = [f.new_path for f in parsed_diff.active_files]
        report.total_additions = parsed_diff.total_additions
        report.total_deletions = parsed_diff.total_deletions

        # 5. Post to GitHub if requested
        markdown_body = format_markdown_report(report)
        head_sha = pr_details.get("head", {}).get("sha")

        if post_review:
            if not head_sha:
                raise ValueError("Could not determine head commit SHA to post formal PR review.")
            event = report.summary.verdict.to_github_event()
            self.github_client.post_pull_request_review(
                repo=repo,
                pr_number=pr_number,
                commit_id=head_sha,
                event=event,
                body=markdown_body,
            )
        elif post_comment:
            self.github_client.post_issue_comment(
                repo=repo,
                pr_number=pr_number,
                comment_body=markdown_body,
            )

        return report

    def review_local_git(
        self,
        base_branch: Optional[str] = None,
        staged_only: bool = False,
        cwd: Optional[str] = None,
    ) -> ReviewReport:
        """Reviews uncommitted or branch changes in the local git repository."""
        raw_diff = get_local_diff(base_branch=base_branch, staged_only=staged_only, cwd=cwd)
        if not raw_diff or not raw_diff.strip():
            target_desc = "staged changes" if staged_only else (f"diff against {base_branch}" if base_branch else "working tree")
            raise ValueError(f"No git diff changes detected for {target_desc}.")

        parsed_diff = parse_unified_diff(raw_diff)
        if not parsed_diff.active_files:
            raise ValueError("All changed files are ignored (e.g. binary or lock files).")

        git_meta = get_local_git_context(cwd=cwd)
        pr_context = f"""Local Git Repository Diff
Current Branch: {git_meta.get('current_branch', 'unknown')}
Latest Commit: {git_meta.get('latest_commit', 'none')}
Base Reference: {base_branch or 'HEAD / Working Tree'}
Mode: {'Staged changes only' if staged_only else 'Working tree changes'}
"""

        diff_text = f"<untrusted_pr_diff>\n{parsed_diff.to_review_text(annotated=self.annotated_diff)}\n</untrusted_pr_diff>"
        report = self.provider.review_diff(
            diff_text=diff_text,
            pr_context=pr_context,
            system_instruction=self.system_instruction,
        )

        report.pr_identifier = f"local:{git_meta.get('current_branch', 'repo')}"
        report.files_analyzed = [f.new_path for f in parsed_diff.active_files]
        report.total_additions = parsed_diff.total_additions
        report.total_deletions = parsed_diff.total_deletions

        return report

    def review_diff_file(self, file_path: str) -> ReviewReport:
        """Reviews diff content read from a file on disk."""
        raw_diff = get_diff_from_file(file_path)
        if not raw_diff or not raw_diff.strip():
            raise ValueError(f"Diff file '{file_path}' is empty.")

        parsed_diff = parse_unified_diff(raw_diff)
        if not parsed_diff.active_files:
            raise ValueError(f"No active code changes found in diff file '{file_path}'.")

        pr_context = f"Patch Diff File: {os.path.basename(file_path)}"
        diff_text = f"<untrusted_pr_diff>\n{parsed_diff.to_review_text(annotated=self.annotated_diff)}\n</untrusted_pr_diff>"

        report = self.provider.review_diff(
            diff_text=diff_text,
            pr_context=pr_context,
            system_instruction=self.system_instruction,
        )

        report.pr_identifier = f"file:{os.path.basename(file_path)}"
        report.files_analyzed = [f.new_path for f in parsed_diff.active_files]
        report.total_additions = parsed_diff.total_additions
        report.total_deletions = parsed_diff.total_deletions

        return report
