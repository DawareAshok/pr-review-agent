import os
import sys
from typing import Optional

# Ensure UTF-8 output encoding on Windows consoles
if sys.platform == "win32":
    try:
        if sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr.encoding.lower() != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import click
from rich.console import Console

from pr_reviewer.engine import ReviewEngine
from pr_reviewer.formatter import format_json_report, format_markdown_report, render_terminal_report


@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.argument("target", required=False)
@click.option(
    "--local", "-l",
    is_flag=True,
    help="Review local git repository changes instead of a remote PR."
)
@click.option(
    "--diff-file", "-f",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to a diff or patch file on disk to review."
)
@click.option(
    "--base", "-b",
    help="Base branch to compare against for local git review (e.g. 'main', 'master')."
)
@click.option(
    "--staged",
    is_flag=True,
    help="For local git review: review only staged changes (--cached)."
)
@click.option(
    "--provider", "-p",
    type=click.Choice(["openai", "gemini", "anthropic", "mock"], case_sensitive=False),
    help="LLM provider to use (default: from DEFAULT_PROVIDER env or 'openai')."
)
@click.option(
    "--model", "-m",
    help="Model name (default: from DEFAULT_MODEL env or 'gpt-4o-mini' for OpenAI)."
)
@click.option(
    "--token",
    help="GitHub Personal Access Token (overrides GITHUB_TOKEN env)."
)
@click.option(
    "--post-review",
    is_flag=True,
    help="Submit a formal GitHub PR review with the verdict (APPROVE, REQUEST_CHANGES, COMMENT)."
)
@click.option(
    "--post-comment",
    is_flag=True,
    help="Post review as a discussion comment on the GitHub PR thread."
)
@click.option(
    "--output-md", "-o",
    type=click.Path(dir_okay=False, writable=True),
    help="Write review report as GitHub Markdown to the specified file."
)
@click.option(
    "--output-json",
    type=click.Path(dir_okay=False, writable=True),
    help="Write review report as structured JSON to the specified file."
)
@click.option(
    "--raw",
    is_flag=True,
    help="Use raw unified diff without explicit line number annotations."
)
@click.option(
    "--quiet", "-q",
    is_flag=True,
    help="Do not display rich interactive report in the terminal."
)
def main(
    target: Optional[str],
    local: bool,
    diff_file: Optional[str],
    base: Optional[str],
    staged: bool,
    provider: Optional[str],
    model: Optional[str],
    token: Optional[str],
    post_review: bool,
    post_comment: bool,
    output_md: Optional[str],
    output_json: Optional[str],
    raw: bool,
    quiet: bool,
):
    """
    Automated AI Pull Request Code Reviewer.

    \b
    Examples:
      pr-review https://github.com/octocat/Hello-World/pull/42
      pr-review octocat/Hello-World#42 --provider gemini
      pr-review --local --base main
      pr-review --local --staged
      pr-review --diff-file changes.patch --provider mock
    """
    console = Console(legacy_windows=False)

    if not target and not local and not diff_file:
        console.print(
            "[bold yellow]No review target specified.[/bold yellow]\n"
            "Provide a GitHub PR URL/identifier, `--local` for working tree, or `--diff-file`.\n"
            "Run [bold cyan]pr-review --help[/bold cyan] for usage instructions."
        )
        sys.exit(1)

    try:
        # Initialize review engine
        with console.status("[bold cyan]Initializing PR Review Engine...[/bold cyan]", spinner="dots"):
            engine = ReviewEngine(
                provider_name=provider,
                model_name=model,
                github_token=token,
                annotated_diff=not raw,
            )

        # Execute review
        if diff_file:
            with console.status(f"[bold cyan]Analyzing diff file '{diff_file}'...[/bold cyan]", spinner="dots"):
                report = engine.review_diff_file(diff_file)
        elif local:
            with console.status("[bold cyan]Analyzing local git changes...[/bold cyan]", spinner="dots"):
                report = engine.review_local_git(base_branch=base, staged_only=staged)
        else:
            with console.status(f"[bold cyan]Fetching and reviewing PR '{target}'...[/bold cyan]", spinner="dots"):
                report = engine.review_github_pr(
                    pr_target=target,  # type: ignore
                    post_review=post_review,
                    post_comment=post_comment,
                )

        # Output terminal display
        if not quiet:
            render_terminal_report(report, console=console)

        # Save to Markdown
        if output_md:
            md_content = format_markdown_report(report)
            with open(output_md, "w", encoding="utf-8") as f:
                f.write(md_content)
            console.print(f"[green]Markdown report saved to:[/green] {output_md}")

        # Save to JSON
        if output_json:
            json_content = format_json_report(report)
            with open(output_json, "w", encoding="utf-8") as f:
                f.write(json_content)
            console.print(f"[green]JSON report saved to:[/green] {output_json}")

        if post_review:
            console.print("[bold green]Formal Pull Request review posted to GitHub successfully.[/bold green]")
        elif post_comment:
            console.print("[bold green]Review comment posted to GitHub PR discussion thread.[/bold green]")

    except Exception as e:
        console.print(f"\n[bold red]Error executing review:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
