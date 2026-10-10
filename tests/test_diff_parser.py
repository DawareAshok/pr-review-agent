from pr_reviewer.diff_parser import parse_unified_diff


SAMPLE_DIFF = """diff --git a/src/calculator.py b/src/calculator.py
index 1234567..89abcdef 100644
--- a/src/calculator.py
+++ b/src/calculator.py
@@ -10,6 +10,8 @@ def divide(a, b):
     if b == 0:
         raise ValueError("Cannot divide by zero")
     return a / b
+
+def multiply(a, b):
+    return a * b
diff --git a/package-lock.json b/package-lock.json
index 1111111..2222222 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,3 +1,3 @@
-{"version": 1}
+{"version": 2}
"""


def test_parse_unified_diff_basic():
    parsed = parse_unified_diff(SAMPLE_DIFF)
    assert len(parsed.files) == 2

    # package-lock.json should be ignored
    active = parsed.active_files
    assert len(active) == 1
    assert active[0].new_path == "src/calculator.py"
    assert active[0].additions == 3
    assert active[0].deletions == 0


def test_annotated_diff_output():
    parsed = parse_unified_diff(SAMPLE_DIFF)
    annotated = parsed.to_review_text(annotated=True)
    assert "### File: src/calculator.py (+3, -0)" in annotated
    assert "L" in annotated
    assert "def multiply(a, b):" in annotated


def test_empty_diff():
    parsed = parse_unified_diff("")
    assert len(parsed.files) == 0
    assert parsed.total_additions == 0
    assert parsed.total_deletions == 0
