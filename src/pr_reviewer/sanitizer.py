import re

# Maximum allowed diff file size (10 MB) to prevent memory exhaustion / DoS
MAX_DIFF_FILE_SIZE = 10 * 1024 * 1024

# Regex patterns for sensitive tokens to redact from logs and exception messages
SENSITIVE_PATTERNS = [
    # Anthropic keys (more specific than sk-)
    (re.compile(r"sk-ant-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE), "sk-ant-[REDACTED]"),
    # OpenAI keys
    (re.compile(r"sk-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE), "sk-[REDACTED]"),
    # GitHub tokens (ghp, gho, ghu, ghs, ghr)
    (re.compile(r"gh[pousr]_[a-zA-Z0-9]{30,}", re.IGNORECASE), "gh_[REDACTED]"),
    # Generic bearer tokens in Authorization headers
    (re.compile(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE), r"\1[REDACTED]"),
    # Google API keys
    (re.compile(r"AIza[0-9A-Za-z-_]{35}"), "AIza[REDACTED]"),
]

# Strict pattern for valid Git references (branches/tags/commits)
# Must not start with '-' or '.', must not contain '..', control chars, spaces, or '~', '^', ':', '?'
GIT_REF_PATTERN = re.compile(r"^(?!/)(?!.*//)(?!.*\.\.)[a-zA-Z0-9_./@\-]+$")

# Strict pattern for GitHub repository full names: 'owner/repo'
GITHUB_REPO_PATTERN = re.compile(r"^[a-zA-Z0-9_.\-]+/[a-zA-Z0-9_.\-]+$")


def sanitize_sensitive_text(text: str) -> str:
    """Masks known sensitive API keys and tokens in strings to prevent credential leakage."""
    if not text:
        return ""
    sanitized = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def validate_git_ref(ref_name: str) -> str:
    """
    Validates that a git reference name (branch, tag, SHA) is safe to pass to git.
    Prevents argument injection (e.g. flags starting with '-') and path traversal.
    """
    cleaned = ref_name.strip()
    if not cleaned:
        raise ValueError("Git reference cannot be empty.")
    if cleaned.startswith("-"):
        raise ValueError(f"Git reference cannot start with a dash ('-') to prevent option injection: '{cleaned}'")
    if ".." in cleaned:
        raise ValueError(f"Git reference cannot contain path traversal ('..'): '{cleaned}'")
    if not GIT_REF_PATTERN.match(cleaned):
        raise ValueError(
            f"Invalid characters in git reference '{cleaned}'. "
            "Only alphanumeric characters, '.', '_', '/', '@', and '-' are permitted."
        )
    return cleaned


def validate_repo_identifier(repo: str) -> str:
    """
    Validates a GitHub repository full name ('owner/repo').
    Prevents path traversal, URL injection, and malformed repository names.
    """
    cleaned = repo.strip()
    if not GITHUB_REPO_PATTERN.match(cleaned):
        raise ValueError(
            f"Invalid GitHub repository identifier: '{repo}'. "
            "Expected 'owner/repository' format containing only alphanumeric characters, '.', '_', or '-'."
        )
    parts = cleaned.split("/")
    if len(parts) != 2 or parts[0] in (".", "..") or parts[1] in (".", ".."):
        raise ValueError(f"Invalid repository segment in '{repo}'.")
    return cleaned
