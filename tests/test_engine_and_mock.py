import json
from pr_reviewer.formatter import format_json_report, format_markdown_report
from pr_reviewer.models import ReviewVerdict, Severity
from pr_reviewer.providers.mock_provider import MockLLMProvider


DIFF_WITH_VULNERABILITY = """### File: src/auth.py (+5, -1)
```diff
@@ -10,3 +10,7 @@ def login(user_input):
-    return authenticate(user_input)
+    # Dangerous eval usage
+    token = eval(user_input)
+    db_password = "supersecret_password_123"
+    return token
```"""


def test_mock_provider_detects_security_issue():
    provider = MockLLMProvider()
    report = provider.review_diff(
        diff_text=DIFF_WITH_VULNERABILITY,
        pr_context="test/repo#1",
        system_instruction="You are a code reviewer."
    )

    assert report.summary.verdict == ReviewVerdict.REQUEST_CHANGES
    assert report.summary.risk_score >= 8
    assert len(report.comments) >= 2

    # Verify critical severity comment was generated
    severities = [c.severity for c in report.comments]
    assert Severity.CRITICAL in severities

    titles = [c.title for c in report.comments]
    assert any("eval" in t.lower() for t in titles)


def test_format_markdown_and_json():
    provider = MockLLMProvider()
    report = provider.review_diff(
        diff_text=DIFF_WITH_VULNERABILITY,
        pr_context="test/repo#1",
        system_instruction="You are a code reviewer."
    )

    md = format_markdown_report(report)
    assert "## ❌ Pull Request Review" in md
    assert "REQUEST_CHANGES" in md
    assert "eval" in md

    json_str = format_json_report(report)
    parsed = json.loads(json_str)
    assert parsed["summary"]["verdict"] == "REQUEST_CHANGES"
