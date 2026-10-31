"""Helpers for reading the data files shipped inside sub-packages."""
from __future__ import annotations

import csv
from pathlib import Path


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    """Rows of a CSV file as dicts (lines starting with '#' are comments, e.g. sources)."""
    with open(path, newline="", encoding="utf-8") as f:
        lines = [line for line in f if not line.lstrip().startswith("#")]
    return list(csv.DictReader(lines))


def csv_source(path: str | Path) -> str:
    """The '# source: ...' comment at the top of a CSV file, if any."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped.lower().startswith("# source:"):
                return stripped.split(":", 1)[1].strip()
            if stripped and not stripped.startswith("#"):
                break
    return ""


def to_float(value) -> float:
    """Float from YAML/CSV values, accepting strings like '210e9'."""
    return float(value)
