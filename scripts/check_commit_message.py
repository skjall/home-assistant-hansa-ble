#!/usr/bin/env python3
"""Reject a commit message that release-please or a reader would choke on.

Two things go wrong repeatedly and both end up published: the subject misses
its Conventional Commits type, so release-please cannot place the change in the
changelog, and the message is written in German, while everything else in this
repository -- code, comments, docs, the changelog on GitHub and PyPI -- is
English.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TYPES = (
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
)
SUBJECT = re.compile(rf"^(?:{'|'.join(TYPES)})(?:\([\w .,/-]+\))?!?: .+")

# Words that are German and are not also English. Short enough to stay a
# tripwire rather than a language detector.
GERMAN = re.compile(
    r"\b(?:der|die|das|und|nicht|nur|wird|wurde|werden|sind|kann|beim|vom|"
    r"eine|einen|einem|einer|dass|weil|damit|statt|ohne|noch|schon|mehr|"
    r"sich|auch|aber|wenn|dann|jetzt|immer|nie|hier|dort|jede|jeden|jedes|"
    r"macht|machen|setzt|setzen|liegt|liegen|steht|stehen|gibt|geben)\b",
    re.IGNORECASE,
)


def main() -> int:
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    body = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    ).strip()
    if not body:
        return 0
    subject = body.splitlines()[0]

    problems = []
    if not SUBJECT.match(subject):
        problems.append(
            f"the subject needs a Conventional Commits type "
            f"({', '.join(TYPES)}), e.g. 'fix: {subject[:40]}'"
        )
    if found := sorted({m.group(0).lower() for m in GERMAN.finditer(body)}):
        problems.append(
            "the message looks German ("
            + ", ".join(found[:6])
            + "); commits, like everything else here, are written in English"
        )

    for problem in problems:
        print(f"  commit message: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
