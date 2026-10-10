# 🤖 PR Review Agent

An intelligent, multi-provider AI agent for automated Pull Request code reviews. Built with Python, Pydantic, Click, and Rich.

---

## ✨ Features

- **Multi-Provider LLM Support**: Works seamlessly with **Google Gemini**, **OpenAI (GPT-4o)**, **Anthropic Claude (3.5 Sonnet)**, or an offline **Mock Provider** for testing.
- **GitHub Pull Request Integration**:
  - Reviews remote PRs by URL (`https://github.com/owner/repo/pull/123`) or shorthand (`owner/repo#123`).
  - Fetches diffs and PR metadata via GitHub REST API.
  - Can post discussion comments or formal Pull Request Reviews (`APPROVE`, `REQUEST_CHANGES`, `COMMENT`).
- **Local Git & Patch File Reviews**:
  - Review your local working tree or staged changes before pushing.
  - Compare feature branches against `main` or any base branch.
  - Review saved `.diff` or `.patch` files.
- **Annotated Line Diff Analysis**:
  - Pre-computes exact new-file line numbers on unified diff lines (`+ L42: ...`), preventing line-number hallucinations.
- **Security & Quality Auditing**:
  - OWASP Top 10 vulnerabilities (SQLi, command injection, secret leakage, RCE).
  - Logic errors, race conditions, unhandled exceptions, and edge cases.
  - Performance bottlenecks and maintainability.
- **Rich Terminal UI & Flexible Exports**:
  - Color-coded verdict banners, risk score meter (1-10), and syntax-highlighted suggested code fixes.
  - Export reports to **GitHub Markdown** (`--output-md`) or structured **JSON** (`--output-json`).

---

## 🚀 Quick Start

### 1. Installation

Clone or enter the repository directory and install dependencies:

```bash
# Install core dependencies
pip install -r requirements.txt

# Install in editable mode
pip install -e .
```

### 2. Configure Environment

Copy `.env.example` to `.env` and set your credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```env
# Default provider: openai, gemini, anthropic, or mock
DEFAULT_PROVIDER=gemini
DEFAULT_MODEL=gemini-2.0-flash

# API Keys (Provide the one corresponding to your provider)
GEMINI_API_KEY=your_gemini_api_key_here
# OPENAI_API_KEY=your_openai_api_key_here
# ANTHROPIC_API_KEY=your_anthropic_api_key_here

# GitHub Token (Required for private repos, posting reviews, or rate limits)
GITHUB_TOKEN=your_github_personal_access_token_here
```

---

## 🛠️ Usage Examples

### 1. Review a Remote GitHub Pull Request
```bash
# Review using URL
pr-review https://github.com/pallets/flask/pull/5000

# Review using shorthand and specific provider
pr-review octocat/Hello-World#42 --provider openai --model gpt-4o-mini
```

### 2. Review Local Git Changes Before Pushing
```bash
# Review uncommitted working tree changes
pr-review --local

# Review only staged changes (git add)
pr-review --local --staged

# Review current branch against main
pr-review --local --base main
```

### 3. Review a Local Patch / Diff File
```bash
pr-review --diff-file ./my_changes.patch --provider mock
```

### 4. Post Review to GitHub
```bash
# Post as a PR discussion comment
pr-review owner/repo#42 --post-comment

# Submit as a formal GitHub PR Review with verdict (APPROVE / REQUEST_CHANGES)
pr-review owner/repo#42 --post-review
```

### 5. Export Reports for CI/CD
```bash
pr-review owner/repo#42 --output-md review.md --output-json review.json --quiet
```

---

## 🧪 Running Tests

```bash
pytest tests -v
```

---

## 📂 Project Structure

```
pr-review-agent/
├── pyproject.toml               # Package configuration & CLI script entrypoint
├── requirements.txt             # Dependencies
├── .env.example                 # Environment variable template
├── src/
│   └── pr_reviewer/
│       ├── __init__.py          # Package exports
│       ├── cli.py               # Click CLI interface
│       ├── engine.py            # ReviewEngine orchestrator
│       ├── models.py            # Pydantic data schemas
│       ├── diff_parser.py       # Unified diff parser & line annotator
│       ├── github_client.py     # GitHub REST API client
│       ├── git_local.py         # Local git command helpers
│       ├── prompts.py           # Senior staff reviewer system prompts
│       ├── formatter.py         # Rich terminal UI & Markdown/JSON formatters
│       └── providers/
│           ├── __init__.py      # Provider factory
│           ├── base.py          # BaseLLMProvider interface
│           ├── openai_provider.py
│           ├── gemini_provider.py
│           ├── anthropic_provider.py
│           └── mock_provider.py
└── tests/
    ├── test_cli.py
    ├── test_diff_parser.py
    ├── test_engine_and_mock.py
    └── test_github_client.py
```
