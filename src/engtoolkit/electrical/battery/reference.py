"""
Precomputed PyBaMM reference results (``electrical/data/pybamm_reference.json``), readable without PyBaMM,
e.g. in the browser. Regenerate with ``python scripts/generate_battery_reference.py``.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

PATH = Path(__file__).resolve().parents[1] / "data" / "pybamm_reference.json"


@lru_cache(maxsize=1)
def load() -> dict:
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)


def cell() -> str:
    return load()["meta"]["cell"]


def temperatures() -> list[float]:
    return sorted({r["T_ambient"] for r in load()["discharge"]})


def c_rates() -> list[float]:
    return sorted({r["c_rate"] for r in load()["discharge"]})


def nearest_temperature(T: float) -> float:
    temps = np.array(temperatures())
    return float(temps[np.argmin(abs(temps - T))])


def discharge(c_rate: float, T_ambient: float) -> dict | None:
    """Discharge run at this C-rate and the nearest ambient temperature in the grid (None if the C-rate is absent)."""
    T = nearest_temperature(T_ambient)
    for r in load()["discharge"]:
        if abs(r["c_rate"] - c_rate) < 1e-9 and r["T_ambient"] == T:
            return r
    return None


def aging(c_rate: float, T_ambient: float) -> dict | None:
    T = nearest_temperature(T_ambient)
    for r in load()["aging"]:
        if abs(r["c_rate"] - c_rate) < 1e-9 and r["T_ambient"] == T:
            return r
    return None
