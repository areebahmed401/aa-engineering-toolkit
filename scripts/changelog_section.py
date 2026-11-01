"""Print the CHANGELOG section for one version.

Usage: python scripts/changelog_section.py VERSION [CHANGELOG_PATH]

Prints the text between ``## [VERSION]`` and the next ``## [`` heading (the heading itself is
omitted). Exits with status 1 if the version is missing or its section is empty.
"""

from __future__ import annotations

import sys
from pathlib import Path


def changelog_section(version: str, text: str) -> str | None:
    """Return the body of the ``## [version]`` section, or None if there is no such heading."""
    lines = text.splitlines()
    marker = f"## [{version}]"
    start = next((i for i, line in enumerate(lines) if line.startswith(marker)), None)
    if start is None:
        return None
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## ["):
            break
        body.append(line)
    return "\n".join(body).strip()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: changelog_section.py VERSION [CHANGELOG_PATH]", file=sys.stderr)
        return 2
    version = argv[1]
    path = Path(argv[2] if len(argv) > 2 else "CHANGELOG.md")
    section = changelog_section(version, path.read_text(encoding="utf-8"))
    if not section:
        print(f"No non-empty section for version {version} in {path}", file=sys.stderr)
        return 1
    print(section)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
