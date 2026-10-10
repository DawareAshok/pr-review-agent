"""
PR Review Agent - Intelligent AI Agent for Automated Pull Request Code Reviews.
"""

__version__ = "0.1.0"

from pr_reviewer.diff_parser import FileDiff, Hunk, ParsedDiff, parse_unified_diff
from pr_reviewer.engine import ReviewEngine
from pr_reviewer.formatter import format_json_report, format_markdown_report, render_terminal_report
from pr_reviewer.github_client import GitHubClient, GitHubClientError, parse_pr_identifier
from pr_reviewer.models import (
    Category,
    PRSummary,
    ReviewComment,
    ReviewReport,
    ReviewVerdict,
    Severity,
)
from pr_reviewer.prompts import DEFAULT_SYSTEM_INSTRUCTION
from pr_reviewer.providers import (
    AnthropicProvider,
    BaseLLMProvider,
    GeminiProvider,
    MockLLMProvider,
    OpenAIProvider,
    get_provider,
)
from pr_reviewer.sanitizer import (
    MAX_DIFF_FILE_SIZE,
    sanitize_sensitive_text,
    validate_git_ref,
    validate_repo_identifier,
)

__all__ = [
    "__version__",
    "ReviewEngine",
    "GitHubClient",
    "GitHubClientError",
    "parse_pr_identifier",
    "parse_unified_diff",
    "ParsedDiff",
    "FileDiff",
    "Hunk",
    "ReviewReport",
    "PRSummary",
    "ReviewComment",
    "Severity",
    "Category",
    "ReviewVerdict",
    "DEFAULT_SYSTEM_INSTRUCTION",
    "BaseLLMProvider",
    "OpenAIProvider",
    "GeminiProvider",
    "AnthropicProvider",
    "MockLLMProvider",
    "get_provider",
    "format_markdown_report",
    "format_json_report",
    "render_terminal_report",
    "sanitize_sensitive_text",
    "validate_git_ref",
    "validate_repo_identifier",
    "MAX_DIFF_FILE_SIZE",
]
