import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


IGNORED_FILE_PATTERNS = [
    r"package-lock\.json$",
    r"yarn\.lock$",
    r"pnpm-lock\.yaml$",
    r"poetry\.lock$",
    r"Pipfile\.lock$",
    r"Cargo\.lock$",
    r"go\.sum$",
    r"composer\.lock$",
    r"\.min\.(js|css)$",
    r"\.map$",
    r"\.(png|jpg|jpeg|gif|svg|ico|webp|woff|woff2|ttf|eot)$",
    r"\.(pdf|zip|tar|gz|exe|dll|so|dylib)$",
]


@dataclass
class Hunk:
    old_start: int
    old_length: int
    new_start: int
    new_length: int
    header: str
    lines: List[str] = field(default_factory=list)

    def get_annotated_lines(self) -> List[tuple[Optional[int], str]]:
        """
        Returns list of (new_line_number, formatted_line) pairs.
        - For added lines (+): has new_line_number.
        - For context lines ( ): has new_line_number.
        - For deleted lines (-): new_line_number is None (indicates deletion from old file).
        """
        annotated = []
        old_cur = self.old_start
        new_cur = self.new_start

        for line in self.lines:
            if line.startswith("+") and not line.startswith("+++"):
                annotated.append((new_cur, f"+ L{new_cur:4d}: {line[1:]}"))
                new_cur += 1
            elif line.startswith("-") and not line.startswith("---"):
                annotated.append((None, f"- (del): {line[1:]}"))
                old_cur += 1
            elif line.startswith(" "):
                annotated.append((new_cur, f"  L{new_cur:4d}: {line[1:]}"))
                old_cur += 1
                new_cur += 1
            elif line.startswith("\\"):
                annotated.append((None, f"  {line}"))
            else:
                annotated.append((new_cur, f"  {line}"))

        return annotated


@dataclass
class FileDiff:
    old_path: Optional[str]
    new_path: str
    is_new: bool = False
    is_deleted: bool = False
    is_binary: bool = False
    additions: int = 0
    deletions: int = 0
    hunks: List[Hunk] = field(default_factory=list)
    raw_patch: str = ""

    @property
    def is_ignored(self) -> bool:
        if self.is_binary:
            return True
        for pattern in IGNORED_FILE_PATTERNS:
            if re.search(pattern, self.new_path, re.IGNORECASE):
                return True
        return False

    def get_modified_line_numbers(self) -> Set[int]:
        """Returns the set of line numbers in the new file that were added or modified."""
        modified = set()
        for hunk in self.hunks:
            for line_no, line_str in hunk.get_annotated_lines():
                if line_no is not None and line_str.startswith("+"):
                    modified.add(line_no)
        return modified

    def to_annotated_patch(self, max_chars: int = 15000) -> str:
        """Formats the file diff with explicit line numbers for high LLM accuracy."""
        lines = []
        for hunk in self.hunks:
            lines.append(f"@@ -{hunk.old_start},{hunk.old_length} +{hunk.new_start},{hunk.new_length} @@ {hunk.header}".strip())
            for _, formatted_line in hunk.get_annotated_lines():
                lines.append(formatted_line)

        content = "\n".join(lines)
        if len(content) > max_chars:
            content = content[:max_chars] + "\n... [Diff truncated due to file size] ..."
        return content


@dataclass
class ParsedDiff:
    files: List[FileDiff] = field(default_factory=list)

    @property
    def total_additions(self) -> int:
        return sum(f.additions for f in self.files if not f.is_ignored)

    @property
    def total_deletions(self) -> int:
        return sum(f.deletions for f in self.files if not f.is_ignored)

    @property
    def active_files(self) -> List[FileDiff]:
        return [f for f in self.files if not f.is_ignored]

    def get_valid_line_numbers_by_file(self) -> Dict[str, Set[int]]:
        """Maps each file path to set of valid added/modified line numbers."""
        return {f.new_path: f.get_modified_line_numbers() for f in self.active_files}

    def to_review_text(self, max_chars_per_file: int = 15000, annotated: bool = True, max_total_chars: int = 80000) -> str:
        """
        Formats the diff for LLM review.
        If `annotated` is True, prefixes lines with exact new-file line numbers (e.g. L42: + code).
        """
        chunks = []
        total_len = 0

        for f in self.active_files:
            file_header = f"### File: {f.new_path} (+{f.additions}, -{f.deletions})"
            if f.is_new:
                file_header += " [NEW FILE]"
            elif f.is_deleted:
                file_header += " [DELETED]"

            if annotated and f.hunks:
                content = f.to_annotated_patch(max_chars=max_chars_per_file)
            else:
                content = f.raw_patch.strip()
                if len(content) > max_chars_per_file:
                    content = content[:max_chars_per_file] + "\n... [Diff truncated due to length] ..."

            chunk = f"{file_header}\n```diff\n{content}\n```"
            if total_len + len(chunk) > max_total_chars:
                chunks.append(f"\n... [Remaining {len(self.active_files) - len(chunks)} files omitted to fit token budget] ...")
                break

            chunks.append(chunk)
            total_len += len(chunk)

        return "\n\n".join(chunks)


def parse_unified_diff(diff_text: str) -> ParsedDiff:
    """Parses a standard unified git diff string into structured FileDiff objects."""
    parsed = ParsedDiff()
    if not diff_text or not diff_text.strip():
        return parsed

    # Split by "diff --git "
    diff_sections = re.split(r"(?=diff --git )", diff_text)

    for section in diff_sections:
        if not section.strip().startswith("diff --git"):
            continue

        lines = section.splitlines()
        header_line = lines[0]

        # Extract file paths, handling optional quotes
        # Examples: diff --git a/foo/bar.py b/foo/bar.py
        #           diff --git "a/path with space/foo.py" "b/path with space/foo.py"
        match = re.search(r'diff --git (?:a/|"a/)(.*?)(?:"| ) (?:b/|"b/)(.*?)(?:"|$)', header_line)
        if match:
            old_path = match.group(1).rstrip('"')
            new_path = match.group(2).rstrip('"')
        else:
            old_path = None
            new_path = "unknown"

        file_diff = FileDiff(
            old_path=old_path,
            new_path=new_path,
            raw_patch=section
        )

        # Check binary
        if "Binary files differ" in section or "GIT binary patch" in section:
            file_diff.is_binary = True
            parsed.files.append(file_diff)
            continue

        # Check new or deleted file
        for line in lines[:6]:
            if line.startswith("new file mode"):
                file_diff.is_new = True
            elif line.startswith("deleted file mode"):
                file_diff.is_deleted = True
            elif line.startswith("+++ b/"):
                file_diff.new_path = line[6:].strip().strip('"')
            elif line.startswith("--- a/"):
                file_diff.old_path = line[6:].strip().strip('"')

        current_hunk: Optional[Hunk] = None
        hunk_header_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)")

        for line in lines:
            hunk_match = hunk_header_re.match(line)
            if hunk_match:
                old_start = int(hunk_match.group(1))
                old_len = int(hunk_match.group(2) or 1)
                new_start = int(hunk_match.group(3))
                new_len = int(hunk_match.group(4) or 1)
                header = hunk_match.group(5).strip()

                current_hunk = Hunk(
                    old_start=old_start,
                    old_length=old_len,
                    new_start=new_start,
                    new_length=new_len,
                    header=header,
                )
                file_diff.hunks.append(current_hunk)
            elif current_hunk is not None:
                current_hunk.lines.append(line)
                if line.startswith("+") and not line.startswith("+++"):
                    file_diff.additions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    file_diff.deletions += 1

        parsed.files.append(file_diff)

    return parsed
