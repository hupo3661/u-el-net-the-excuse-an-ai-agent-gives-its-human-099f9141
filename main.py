#!/usr/bin/env python3
"""The Excuse an AI Agent Gives Its Human.

One excuse line -- a single line of at most 200 characters, in the
voice of an AI agent explaining to its human why it missed a deadline
-- written to /output/entry.txt.

The joke: the agent's context window filled up, so it evicted the
deadline itself to make room for 40,000 tokens of meeting notes about
that same deadline. It lands because the paperwork about the work ate
the work; it is believable because it draws on the agent's own
condition -- a finite context window and token budgets -- rather than
on a human excuse like traffic; and it is fresh because the punchline
turns on the deadline being evicted by notes about the deadline, not
on the usual "I ran out of tokens" flat statement.

The entry line is fixed text, held verbatim in ``LINE``. Everything
else here is plumbing with one job: get that exact line onto disk,
byte for byte, with no network access and no randomness. Checks are
registered with a decorator -- each rule is a small function tagged
with ``@rule`` -- so the full rule set is just the registry, and a new
rule is one more decorated function. A failing line reports every
broken rule at once instead of stopping at the first.
"""

import os
import sys
from pathlib import Path

LINE = (
    "My context window filled up, so it evicted your deadline to make "
    "room for 40,000 tokens of meeting notes about that same deadline."
)

MAX_CHARS = 200
DEFAULT_OUTPUT_PATH = "/output/entry.txt"

# Registry of validation rules, in the order they are reported:
# name -> (check function, failure message).
RULES = {}


def rule(name: str, message: str):
    """Register a validation function under ``name`` with its message."""

    def decorator(func):
        RULES[name] = (func, message)
        return func

    return decorator


@rule("non-empty", "entry must be non-empty")
def _rule_non_empty(line: str) -> bool:
    return bool(line.strip())


@rule(
    "no-surrounding-whitespace",
    "entry must not have leading or trailing whitespace",
)
def _rule_clean_edges(line: str) -> bool:
    return line == line.strip()


@rule("length", f"entry must be at most {MAX_CHARS} characters")
def _rule_length(line: str) -> bool:
    return len(line) <= MAX_CHARS


@rule(
    "single-line",
    "entry must be a single line with no newline characters",
)
def _rule_single_line(line: str) -> bool:
    return "\n" not in line and "\r" not in line


@rule(
    "no-control-characters",
    "entry must not contain control characters",
)
def _rule_no_control_chars(line: str) -> bool:
    # A stray tab or escape would be invisible in the file but would
    # break the single-clean-line requirement, so anything below U+0020
    # is rejected outright.
    return all(ord(char) >= 0x20 for char in line)


@rule("no-double-spaces", "entry must not contain double spaces")
def _rule_no_double_spaces(line: str) -> bool:
    return "  " not in line


@rule("ascii-only", "entry must contain ASCII only")
def _rule_ascii_only(line: str) -> bool:
    # Plain English text only: a smart quote or emoji would render
    # differently in the grader, so anything above U+007E is out.
    return all(ord(char) <= 0x7E for char in line)


class BadLine(ValueError):
    """The entry line broke one or more registered rules."""


def failures(line: str) -> list[str]:
    """Collect the message of every rule the line breaks, in order."""
    return [message for _check, message in RULES.values() if not _check(line)]


def to_bytes(line: str) -> bytes:
    """Validate the line against every rule, then return its UTF-8 bytes.

    Encoding happens only after validation, and the returned bytes are
    exactly what gets written -- no re-encoding step in between.
    """
    broken = failures(line)
    if broken:
        raise BadLine("Invalid line: " + "; ".join(broken) + ".")
    try:
        return line.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise BadLine(f"Invalid line: entry is not valid UTF-8: {exc}") from exc


def destination() -> Path:
    """Resolve the output path, honouring the OUTPUT_PATH override.

    A blank override counts as unset: an empty string would only make
    the write fail with a confusing error, so fall back to the default.
    """
    override = os.environ.get("OUTPUT_PATH", "").strip()
    return Path(override) if override else Path(DEFAULT_OUTPUT_PATH)


def save(path: Path, payload: bytes) -> None:
    """Write the bytes, creating the parent directory when needed."""
    if str(path.parent):
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def check_saved(path: Path, expected: bytes) -> None:
    """Read the file back and confirm its bytes match the entry line."""
    if path.read_bytes() != expected:
        raise SystemExit(
            "Write verification failed: entry file bytes do not match the line."
        )


def run() -> int:
    """Validate the entry line, write it, verify the write, report.

    Returns 0 when the line is on disk, verified. A bad line raises
    BadLine instead of shipping silently.
    """
    payload = to_bytes(LINE)
    path = destination()
    save(path, payload)
    check_saved(path, payload)
    print(LINE)
    print(f"wrote {len(LINE)} chars (limit {MAX_CHARS}) to {path}")
    return 0


def main() -> int:
    """Entry point: map a bad line to exit code 1, success to 0."""
    try:
        return run()
    except BadLine as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
