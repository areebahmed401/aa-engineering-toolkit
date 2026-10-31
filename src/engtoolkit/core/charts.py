"""
Chart specifications: tools describe their charts as data (SI units), and each front end draws them
(Plotly in the web app, matplotlib in notebooks via ``Chart.to_figure()``).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Literal

import numpy as np


def _clean(values) -> list:
    out = []
    for v in np.asarray(values, dtype=float).tolist():
        out.append(None if (v is None or not math.isfinite(v)) else v)
    return out


@dataclass
class Series:
    name: str
    x: list
    y: list
    mode: Literal["lines", "markers", "lines+markers"] = "lines"
    axis: Literal["y", "y2"] = "y"
    fill: bool = False      # fill to zero (shear/moment diagrams)
    dash: bool = False
    color: str | None = None

    def __post_init__(self):
        self.x = _clean(self.x)
        self.y = _clean(self.y)


@dataclass
class Shape:
    """Closed polygon (e.g. a cross-section outline, with holes drawn on top in the background colour)."""
    points: list
    hole: bool = False

    def __post_init__(self):
        self.points = [[float(x), float(y)] for x, y in self.points]


@dataclass
class Chart:
    id: str
    title: str
    x_label: str
    x_unit: str = ""
    y_label: str = ""
    y_unit: str = ""
    series: list[Series] = field(default_factory=list)
    y2_label: str = ""
    y2_unit: str = ""
    log_x: bool = False
    log_y: bool = False
    equal_aspect: bool = False
    shapes: list[Shape] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_figure(self):
        """Render with matplotlib (for notebooks)."""
        from .plotting import new_figure, styled
        with styled():
            fig, ax = new_figure(figsize=(8, 4.5))
            ax2 = ax.twinx() if any(s.axis == "y2" for s in self.series) else None
            from matplotlib.patches import Polygon
            for shape in self.shapes:
                ax.add_patch(Polygon(shape.points, closed=True, facecolor="white" if shape.hole else "#C7D2FE",
                                     edgecolor="#4F46E5", lw=1.5))
            for s in self.series:
                target = ax2 if s.axis == "y2" else ax
                style = {"lines": "-", "markers": "o", "lines+markers": "o-"}[s.mode]
                x = np.array(s.x, dtype=float)
                y = np.array(s.y, dtype=float)
                target.plot(x, y, style, label=s.name, ls="--" if s.dash else None, color=s.color)
                if s.fill:
                    target.fill_between(x, y, alpha=0.15, color=s.color)
            ax.set(title=self.title, xlabel=f"{self.x_label} [{self.x_unit}]" if self.x_unit else self.x_label,
                   ylabel=f"{self.y_label} [{self.y_unit}]" if self.y_unit else self.y_label)
            if self.log_x:
                ax.set_xscale("log")
            if self.log_y:
                ax.set_yscale("log")
            if self.equal_aspect:
                ax.set_aspect("equal")
                ax.autoscale_view()
            if ax2 is not None:
                ax2.set_ylabel(f"{self.y2_label} [{self.y2_unit}]" if self.y2_unit else self.y2_label)
                ax2.grid(False)
            handles = ax.get_legend_handles_labels()
            if ax2 is not None:
                h2 = ax2.get_legend_handles_labels()
                handles = (handles[0] + h2[0], handles[1] + h2[1])
            if handles[0]:
                ax.legend(*handles)
        return fig
