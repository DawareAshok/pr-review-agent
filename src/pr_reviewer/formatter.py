import json
from typing import Optional
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.markdown import Markdown

from pr_reviewer.models import ReviewReport, ReviewVerdict, Severity


def render_terminal_report(report: ReviewReport, console: Optional[Console] = None) -> None:
    """Renders a rich, interactive, color-coded terminal review report."""
    if console is None:
        console = Console(legacy_windows=False)

    summary = report.summary

    # Determine verdict color and styling
    verdict_styles = {
        ReviewVerdict.APPROVED: ("green", "✅ APPROVED", "Good to merge"),
        ReviewVerdict.REQUEST_CHANGES: ("red", "❌ REQUEST CHANGES", "Critical or blocking issues found"),
        ReviewVerdict.COMMENT: ("yellow", "💬 COMMENT", "Review notes and observations"),
    }
    color, verdict_label, verdict_sub = verdict_styles.get(
        summary.verdict, ("white", summary.verdict.value, "")
    )

    # Risk score meter
    risk_color = "green" if summary.risk_score <= 3 else ("yellow" if summary.risk_score <= 6 else "red")
    risk_bar = "█" * summary.risk_score + "░" * (10 - summary.risk_score)

    header_text = Text()
    header_text.append(f"{verdict_label}\n", style=f"bold {color}")
    header_text.append(f"{verdict_sub}\n\n", style="italic dim")
    header_text.append("Target: ", style="bold")
    header_text.append(f"{report.pr_identifier}\n", style="cyan")
    header_text.append("Diff Stats: ", style="bold")
    header_text.append(f"+{report.total_additions} ", style="green")
    header_text.append(f"-{report.total_deletions} ", style="red")
    header_text.append(f"across {len(report.files_analyzed)} files\n", style="dim")
    header_text.append("Risk Score: ", style="bold")
    header_text.append(f"[{risk_bar}] {summary.risk_score}/10\n", style=f"bold {risk_color}")

    console.print(Panel(header_text, title="🤖 AI PR Review Verdict", border_style=color, expand=False))

    # Overview
    console.print("\n[bold]📋 Summary & Impact:[/bold]")
    console.print(Markdown(summary.overview))

    # Key Strengths
    if summary.key_strengths:
        console.print("\n[bold green]🌟 Key Strengths:[/bold green]")
        for strength in summary.key_strengths:
            console.print(f"  [green]✔[/green] {strength}")

    # Key Concerns
    if summary.key_concerns:
        console.print("\n[bold red]⚠️ Key Concerns:[/bold red]")
        for concern in summary.key_concerns:
            console.print(f"  [red]✖[/red] {concern}")

    # Detailed Findings
    if report.comments:
        console.print(f"\n[bold]🔍 Review Findings ({len(report.comments)}):[/bold]\n")

        # Sort comments by severity
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.WARNING: 1,
            Severity.SUGGESTION: 2,
            Severity.INFO: 3,
        }
        sorted_comments = sorted(report.comments, key=lambda c: severity_order.get(c.severity, 99))

        for idx, comment in enumerate(sorted_comments, 1):
            badge_color = comment.severity.color
            location = f"{comment.file_path}"
            if comment.line_number is not None:
                location += f":{comment.line_number}"

            title_text = Text()
            title_text.append(f"#{idx} ", style="dim")
            title_text.append(f"{comment.severity.icon} [{comment.severity.value}] ", style=f"bold {badge_color}")
            title_text.append(f"{comment.category.icon} {comment.title} ", style="bold white")
            title_text.append(f"({location})", style="cyan dim")

            renderables = [
                Text(comment.explanation, style="white")
            ]

            if comment.suggested_fix:
                renderables.append(Text("\nSuggested Fix:", style="bold italic green"))
                # Detect language based on file extension
                lang = "python"
                if comment.file_path.endswith((".js", ".jsx", ".ts", ".tsx")):
                    lang = "typescript"
                elif comment.file_path.endswith((".json", ".yaml", ".yml")):
                    lang = "yaml"
                elif comment.file_path.endswith(".go"):
                    lang = "go"
                elif comment.file_path.endswith(".rs"):
                    lang = "rust"
                renderables.append(
                    Syntax(comment.suggested_fix.strip(), lang, theme="monokai", line_numbers=False)
                )

            console.print(Panel(
                Group(*renderables),
                title=title_text,
                border_style=badge_color,
                expand=True
            ))
    else:
        console.print("\n[bold green]🎉 No code issues found! Ready to merge.[/bold green]")


def format_markdown_report(report: ReviewReport) -> str:
    """Formats the review report as GitHub-flavored Markdown."""
    summary = report.summary

    verdict_emoji = {
        ReviewVerdict.APPROVED: "✅",
        ReviewVerdict.REQUEST_CHANGES: "❌",
        ReviewVerdict.COMMENT: "💬",
    }.get(summary.verdict, "📝")

    lines = [
        f"## {verdict_emoji} Pull Request Review: {summary.title}",
        "",
        f"- **Verdict:** `{summary.verdict.value}`",
        f"- **Risk Score:** `{summary.risk_score} / 10`",
        f"- **Diff Stats:** `+{report.total_additions} / -{report.total_deletions}` across {len(report.files_analyzed)} files",
        "",
        "### 📋 Overview",
        summary.overview,
        "",
    ]

    if summary.key_strengths:
        lines.append("### 🌟 Key Strengths")
        for s in summary.key_strengths:
            lines.append(f"- {s}")
        lines.append("")

    if summary.key_concerns:
        lines.append("### ⚠️ Key Concerns")
        for c in summary.key_concerns:
            lines.append(f"- {c}")
        lines.append("")

    if report.comments:
        lines.append(f"### 🔍 Detailed Findings ({len(report.comments)})")
        lines.append("")

        for comment in report.comments:
            loc = f"`{comment.file_path}`"
            if comment.line_number is not None:
                loc = f"`{comment.file_path}:{comment.line_number}`"

            lines.append(f"#### {comment.severity.icon} [{comment.severity.value}] {comment.title}")
            lines.append(f"**Location:** {loc} | **Category:** {comment.category.icon} `{comment.category.value}`")
            lines.append("")
            lines.append(comment.explanation)
            lines.append("")

            if comment.suggested_fix:
                lines.append("```suggestion")
                lines.append(comment.suggested_fix.strip())
                lines.append("```")
                lines.append("")
    else:
        lines.append("### 🎉 No issues identified. Looks good to merge!")

    lines.append("---")
    lines.append("*Generated automatically by [PR Review Agent](https://github.com/pr-review-agent)*")

    return "\n".join(lines)


def format_json_report(report: ReviewReport, indent: int = 2) -> str:
    """Serializes the review report into formatted JSON string."""
    return report.model_dump_json(indent=indent)
