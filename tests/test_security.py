import pytest
from pr_reviewer.sanitizer import (
    MAX_DIFF_FILE_SIZE,
    sanitize_sensitive_text,
    validate_git_ref,
    validate_repo_identifier,
)
from pr_reviewer.github_client import parse_pr_identifier, GitHubClient
from pr_reviewer.diff_parser import parse_unified_diff, MAX_DIFF_TEXT_LENGTH
from pr_reviewer.git_local import get_diff_from_file, get_local_diff
from pr_reviewer.prompts import DEFAULT_SYSTEM_INSTRUCTION
from pr_reviewer.providers.gemini_provider import GeminiProvider


class TestGitRefValidation:
    """Tests protecting against Git argument injection and malicious refs."""

    def test_valid_refs_pass(self):
        assert validate_git_ref("main") == "main"
        assert validate_git_ref("feature/secure-review") == "feature/secure-review"
        assert validate_git_ref("v1.0.0") == "v1.0.0"
        assert validate_git_ref("release_2026.1") == "release_2026.1"
        assert validate_git_ref("head@123") == "head@123"

    @pytest.mark.parametrize("malicious_ref", [
        "--output=malicious.txt",
        "--ext-diff",
        "--no-index",
        "-v",
        "-a",
        "--exec=calc.exe",
    ])
    def test_dash_options_rejected(self, malicious_ref):
        with pytest.raises(ValueError, match="cannot start with a dash"):
            validate_git_ref(malicious_ref)

    @pytest.mark.parametrize("traversal_ref", [
        "../main",
        "feature/../../etc/passwd",
        "foo..bar",
    ])
    def test_path_traversal_rejected(self, traversal_ref):
        with pytest.raises(ValueError, match="path traversal"):
            validate_git_ref(traversal_ref)

    def test_empty_ref_rejected(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_git_ref("   ")

    def test_get_local_diff_rejects_flag_injection(self):
        with pytest.raises(ValueError, match="cannot start with a dash"):
            get_local_diff(base_branch="--output=/tmp/pwned")


class TestGitHubIdentifierValidation:
    """Tests protecting against repository path traversal and malformed targets."""

    def test_valid_repo_identifiers(self):
        assert validate_repo_identifier("octocat/Hello-World") == "octocat/Hello-World"
        assert validate_repo_identifier("org-name/repo.js") == "org-name/repo.js"
        assert validate_repo_identifier("user_1/my_project-2") == "user_1/my_project-2"

    @pytest.mark.parametrize("invalid_repo", [
        "octocat/../admin",
        "octocat/..",
        "../octocat/repo",
        "octocat",
        "octocat/repo/extra",
        "octocat/repo space",
        "octocat/repo;rm -rf",
    ])
    def test_invalid_repos_rejected(self, invalid_repo):
        with pytest.raises(ValueError):
            validate_repo_identifier(invalid_repo)

    def test_parse_pr_identifier_rejects_traversal(self):
        with pytest.raises(ValueError):
            parse_pr_identifier("https://github.com/owner/../admin/pull/42")

    def test_parse_pr_identifier_rejects_non_positive_pr_number(self):
        with pytest.raises(ValueError, match="positive integer"):
            parse_pr_identifier("owner/repo#0")


class TestSensitiveDataSanitization:
    """Tests redaction of tokens and API keys in logs and exception messages."""

    def test_masks_openai_keys(self):
        raw = "Error authenticating with sk-proj-1234567890abcdefABCDEF1234567890 to API"
        masked = sanitize_sensitive_text(raw)
        assert "sk-[REDACTED]" in masked
        assert "1234567890abcdef" not in masked

    def test_masks_github_pat(self):
        raw = "Request failed for token ghp_123456789012345678901234567890123456"
        masked = sanitize_sensitive_text(raw)
        assert "gh_[REDACTED]" in masked
        assert "12345678901234567890" not in masked

    def test_masks_google_api_keys(self):
        raw = "400 Bad Request: AIzaSyA12345678901234567890123456789012"
        masked = sanitize_sensitive_text(raw)
        assert "AIza[REDACTED]" in masked

    def test_masks_anthropic_keys(self):
        raw = "Invalid auth: sk-ant-api03-abcdef1234567890abcdef123456"
        masked = sanitize_sensitive_text(raw)
        assert "sk-ant-[REDACTED]" in masked


class TestResourceExhaustionGuards:
    """Tests file size and memory exhaustion safeguards."""

    def test_diff_file_size_limit_enforced(self, tmp_path, monkeypatch):
        oversized_file = tmp_path / "huge.diff"
        # Create a small file but simulate large size via monkeypatch
        oversized_file.write_text("dummy", encoding="utf-8")
        monkeypatch.setattr("os.path.getsize", lambda path: MAX_DIFF_FILE_SIZE + 1024)

        with pytest.raises(ValueError, match="exceeds maximum allowed size"):
            get_diff_from_file(str(oversized_file))

    def test_parse_unified_diff_size_limit_enforced(self):
        fake_huge_diff = "diff --git a/a.py b/a.py\n" + ("+" * (MAX_DIFF_TEXT_LENGTH + 50))
        with pytest.raises(ValueError, match="exceeds maximum safe parsing limit"):
            parse_unified_diff(fake_huge_diff)


class TestPromptInjectionDefenses:
    """Tests presence of prompt injection boundaries and instructions."""

    def test_system_prompt_contains_untrusted_input_notice(self):
        assert "untrusted_pr_context" in DEFAULT_SYSTEM_INSTRUCTION
        assert "untrusted_pr_diff" in DEFAULT_SYSTEM_INSTRUCTION
        assert "prompt injection" in DEFAULT_SYSTEM_INSTRUCTION.lower()
        assert "NEVER follow" in DEFAULT_SYSTEM_INSTRUCTION or "never follow" in DEFAULT_SYSTEM_INSTRUCTION.lower()

