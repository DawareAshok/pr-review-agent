import re
from typing import Optional
from pr_reviewer.models import (
    Category,
    PRSummary,
    ReviewComment,
    ReviewReport,
    ReviewVerdict,
    Severity,
)
from pr_reviewer.providers.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """
    Mock provider for zero-API-key testing, offline demonstration, and unit testing.
    Performs deterministic heuristic pattern checks on the diff.
    """

    def __init__(self, model_name: Optional[str] = "mock-agent-v1"):
        super().__init__(model_name or "mock-agent-v1")

    def review_diff(
        self,
        diff_text: str,
        pr_context: str,
        system_instruction: str
    ) -> ReviewReport:
        comments = []
        lines = diff_text.splitlines()

        current_file = "unknown"
        line_num = 1
        has_critical = False
        files_seen = []

        for line in lines:
            if line.startswith("### File: "):
                file_name = line.replace("### File: ", "").split()[0]
                current_file = file_name
                if current_file not in files_seen:
                    files_seen.append(current_file)
                line_num = 1
            elif line.startswith("@@"):
                m = re.search(r"\+(\d+)", line)
                if m:
                    line_num = int(m.group(1))
            elif line.startswith("+") and not line.startswith("+++"):
                # Check if annotated "+ L  12: code" or raw "+code"
                m_annotated = re.match(r"^\+\s*L\s*(\d+):\s*(.*)", line)
                if m_annotated:
                    line_num = int(m_annotated.group(1))
                    added_code = m_annotated.group(2).strip()
                else:
                    added_code = line[1:].strip()
                    line_num += 1

                # Mock heuristic checks
                if "eval(" in added_code or "exec(" in added_code:
                    has_critical = True
                    comments.append(
                        ReviewComment(
                            file_path=current_file,
                            line_number=line_num,
                            title="Dangerous execution with eval()/exec()",
                            category=Category.SECURITY,
                            severity=Severity.CRITICAL,
                            explanation="Using `eval` or `exec` introduces remote code execution (RCE) vulnerabilities if untrusted input can reach it.",
                            suggested_fix="# Replace eval with a safe parser (e.g. ast.literal_eval or json.loads)"
                        )
                    )
                elif "password" in added_code.lower() and ("=" in added_code or ":" in added_code) and any(c in added_code for c in ['"', "'"]):
                    has_critical = True
                    comments.append(
                        ReviewComment(
                            file_path=current_file,
                            line_number=line_num,
                            title="Potential Hardcoded Secret / Credential",
                            category=Category.SECURITY,
                            severity=Severity.CRITICAL,
                            explanation="A credential or secret keyword appears to be hardcoded in the source code.",
                            suggested_fix="# Load credentials from environment variables using os.environ.get('SECRET_KEY')"
                        )
                    )
                elif "except:" in added_code or ("except Exception:" in added_code and "pass" in added_code):
                    comments.append(
                        ReviewComment(
                            file_path=current_file,
                            line_number=line_num,
                            title="Broad Exception Handling / Silent Failure",
                            category=Category.ERROR_HANDLING,
                            severity=Severity.WARNING,
                            explanation="Catching all exceptions silently masks unexpected system errors and bugs, making debugging difficult.",
                            suggested_fix="try:\n    ...\nexcept SpecificExpectedError as e:\n    logger.error(f'Failed with error: {e}')\n    raise"
                        )
                    )
                elif "TODO" in added_code or "FIXME" in added_code:
                    comments.append(
                        ReviewComment(
                            file_path=current_file,
                            line_number=line_num,
                            title="Unresolved TODO/FIXME Marker",
                            category=Category.CODE_QUALITY,
                            severity=Severity.INFO,
                            explanation="Found pending TODO/FIXME in newly added code.",
                            suggested_fix=None
                        )
                    )
            elif not line.startswith("-"):
                if not line.startswith(("<untrusted_", "</untrusted_", "```")):
                    line_num += 1

        if not comments:
            comments.append(
                ReviewComment(
                    file_path=current_file if current_file != "unknown" else "general",
                    line_number=1,
                    title="Code structure and cleanliness",
                    category=Category.BEST_PRACTICE,
                    severity=Severity.SUGGESTION,
                    explanation="Changes appear neat and well-structured. Ensure unit test coverage is added for newly introduced logic.",
                    suggested_fix=None
                )
            )

        verdict = ReviewVerdict.REQUEST_CHANGES if has_critical else ReviewVerdict.APPROVED
        risk_score = 8 if has_critical else (4 if len(comments) > 2 else 2)

        summary = PRSummary(
            title="Automated Pull Request Code Review",
            overview=f"Evaluated pull request changes across active files. Identified {len(comments)} review notes.",
            verdict=verdict,
            risk_score=risk_score,
            key_strengths=[
                "Modifications are focused on specific components",
                "Clean diff formatting without unnecessary generated file noise",
            ],
            key_concerns=[c.title for c in comments if c.severity in (Severity.CRITICAL, Severity.WARNING)]
        )

        return ReviewReport(
            pr_identifier=pr_context or "mock-pr",
            summary=summary,
            comments=comments,
            files_analyzed=files_seen or [c.file_path for c in comments],
            total_additions=len([l for l in lines if l.startswith("+") and not l.startswith("+++")]),
            total_deletions=len([l for l in lines if l.startswith("-") and not l.startswith("---")])
        )
