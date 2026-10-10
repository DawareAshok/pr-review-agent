from click.testing import CliRunner
from pr_reviewer.cli import main


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Automated AI Pull Request Code Reviewer." in result.output
    assert "--local" in result.output
    assert "--diff-file" in result.output


def test_cli_no_args():
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code == 1
    assert "No review target specified" in result.output


def test_cli_diff_file_mock_provider(tmp_path):
    diff_file = tmp_path / "sample.diff"
    diff_file.write_text(
        """diff --git a/app.py b/app.py
index 0000000..1111111 100644
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
 def run():
+    token = eval("1+1")
     return True
""",
        encoding="utf-8"
    )

    out_md = tmp_path / "review.md"
    out_json = tmp_path / "review.json"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--diff-file", str(diff_file),
            "--provider", "mock",
            "--output-md", str(out_md),
            "--output-json", str(out_json),
            "--quiet",
        ]
    )

    assert result.exit_code == 0
    assert out_md.exists()
    assert out_json.exists()
    assert "REQUEST_CHANGES" in out_md.read_text(encoding="utf-8")
