"""
Result objects shared by every discipline.

A result is a dataclass whose fields carry ``unit`` and ``label`` metadata, so notebooks,
the web app, CSV exports and reports can all present it the same way.

    @dataclass
    class PipeDropResult(Result):
        dp: float = rfield("Pa", "Pressure drop")
        velocity: float = rfield("m/s", "Velocity")
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any

import numpy as np


def rfield(unit: str = "", label: str = "", default: Any = dataclasses.MISSING,
           summary: bool = True, **kwargs):
    """Dataclass field with unit/label metadata. ``summary=False`` hides arrays from result cards."""
    meta = {"unit": unit, "label": label, "summary": summary}
    if default is not dataclasses.MISSING:
        kwargs["default"] = default
    return field(metadata=meta, **kwargs)


def _plain(value: Any) -> Any:
    """Convert numpy types and nested results into JSON-friendly Python values."""
    if isinstance(value, Result):
        return value.to_dict()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


@dataclass
class Result:
    """Base class for calculation results."""

    def to_dict(self) -> dict[str, Any]:
        return {f.name: _plain(getattr(self, f.name)) for f in dataclasses.fields(self)}

    def fields_info(self) -> list[dict[str, Any]]:
        """Name, label, unit and value for each field, in declaration order."""
        info = []
        for f in dataclasses.fields(self):
            meta = f.metadata
            info.append({
                "name": f.name,
                "label": meta.get("label") or f.name,
                "unit": meta.get("unit", ""),
                "summary": meta.get("summary", True),
                "value": _plain(getattr(self, f.name)),
            })
        return info

    def summary(self) -> dict[str, Any]:
        """Scalar fields only, keyed by label with the unit appended (for tables and cards)."""
        out = {}
        for item in self.fields_info():
            value = item["value"]
            if not item["summary"] or isinstance(value, (list, dict)):
                continue
            key = f"{item['label']} [{item['unit']}]" if item["unit"] else item["label"]
            out[key] = value
        return out

    def to_dataframe(self):
        import pandas as pd
        rows = [{"quantity": k, "value": v} for k, v in self.summary().items()]
        return pd.DataFrame(rows)

    def _repr_markdown_(self) -> str:  # nice display in notebooks
        lines = [f"**{type(self).__name__}**", "", "| Quantity | Value |", "|---|---|"]
        for key, value in self.summary().items():
            shown = f"{value:.6g}" if isinstance(value, float) else value
            lines.append(f"| {key} | {shown} |")
        return "\n".join(lines)
