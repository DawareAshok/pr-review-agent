from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "CRITICAL"      # Security vulnerabilities, crashes, data loss, breaking changes
    WARNING = "WARNING"        # Edge cases, unhandled exceptions, performance bottlenecks
    SUGGESTION = "SUGGESTION"  # Readability, style improvements, minor optimizations
    INFO = "INFO"              # Educational note or minor observation

    @property
    def icon(self) -> str:
        return {
            Severity.CRITICAL: "🚨",
            Severity.WARNING: "⚠️",
            Severity.SUGGESTION: "💡",
            Severity.INFO: "ℹ️",
        }.get(self, "•")

    @property
    def color(self) -> str:
        return {
            Severity.CRITICAL: "red",
            Severity.WARNING: "yellow",
            Severity.SUGGESTION: "cyan",
            Severity.INFO: "blue",
        }.get(self, "white")


class Category(str, Enum):
    SECURITY = "SECURITY"
    BUG_RISK = "BUG_RISK"
    PERFORMANCE = "PERFORMANCE"
    CODE_QUALITY = "CODE_QUALITY"
    ERROR_HANDLING = "ERROR_HANDLING"
    TYPING_AND_DOCS = "TYPING_AND_DOCS"
    BEST_PRACTICE = "BEST_PRACTICE"

    @property
    def icon(self) -> str:
        return {
            Category.SECURITY: "🔒",
            Category.BUG_RISK: "🐛",
            Category.PERFORMANCE: "⚡",
            Category.CODE_QUALITY: "✨",
            Category.ERROR_HANDLING: "🛡️",
            Category.TYPING_AND_DOCS: "📝",
            Category.BEST_PRACTICE: "📐",
        }.get(self, "📌")


class ReviewVerdict(str, Enum):
    APPROVED = "APPROVED"                    # Good to merge, only minor suggestions or clean
    REQUEST_CHANGES = "REQUEST_CHANGES"      # Has critical bugs or security risks
    COMMENT = "COMMENT"                      # Has questions or warnings that should be addressed

    def to_github_event(self) -> str:
        """Map verdict enum to valid GitHub review API event string."""
        mapping = {
            ReviewVerdict.APPROVED: "APPROVE",
            ReviewVerdict.REQUEST_CHANGES: "REQUEST_CHANGES",
            ReviewVerdict.COMMENT: "COMMENT",
        }
        return mapping.get(self, "COMMENT")


class ReviewComment(BaseModel):
    file_path: str = Field(description="Relative path of the file being reviewed")
    line_number: Optional[int] = Field(
        default=None, 
        description="Specific line number in the new/modified file where the issue occurs, or None if file-level"
    )
    title: str = Field(description="Short, punchy summary of the issue (e.g. 'SQL Injection Vulnerability')")
    category: Category = Field(description="The primary category of the issue")
    severity: Severity = Field(description="Severity rating of the issue")
    explanation: str = Field(description="Detailed explanation of why this is a concern and the potential impact")
    suggested_fix: Optional[str] = Field(
        default=None, 
        description="Suggested replacement code or guidance to fix the issue"
    )


class PRSummary(BaseModel):
    title: str = Field(description="Concise description of the pull request intent")
    overview: str = Field(description="Executive summary of the changes made and their architectural impact")
    verdict: ReviewVerdict = Field(description="Overall PR review decision (APPROVED, REQUEST_CHANGES, COMMENT)")
    risk_score: int = Field(
        ge=1, 
        le=10, 
        description="Risk score from 1 (minimal risk) to 10 (high risk, critical regressions/vulnerabilities)"
    )
    key_strengths: List[str] = Field(
        default_factory=list, 
        description="Things done well in this PR (positive feedback)"
    )
    key_concerns: List[str] = Field(
        default_factory=list, 
        description="Key concerns or questions that must be addressed before merging"
    )


class ReviewReport(BaseModel):
    pr_identifier: str = Field(description="Identifier of the PR or local diff (e.g. 'owner/repo#42' or 'local-working-tree')")
    summary: PRSummary = Field(description="High-level summary and review verdict")
    comments: List[ReviewComment] = Field(
        default_factory=list, 
        description="Specific inline and file-level review findings"
    )
    files_analyzed: List[str] = Field(default_factory=list, description="List of files included in the analysis")
    total_additions: int = Field(default=0, description="Total added lines in reviewed diff")
    total_deletions: int = Field(default=0, description="Total deleted lines in reviewed diff")
