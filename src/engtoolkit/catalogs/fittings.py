"""Fittings and valves: Crane L/D ratios and supplier costs."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from engtoolkit.core.data import read_csv_rows

DATA = Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=1)
def crane_le_over_d() -> dict[str, float]:
    """Equivalent length ratio L/D per fitting type (Crane TP-410)."""
    return {r["fitting_type"]: float(r["le_over_d"]) for r in read_csv_rows(DATA / "crane_le_over_d.csv")}


def fitting_types() -> list[str]:
    return list(crane_le_over_d())


@lru_cache(maxsize=1)
def _fitting_costs() -> dict[tuple[str, int, str], float]:
    return {(r["type"], int(r["dn"]), r["material"]): float(r["cost_usd"])
            for r in read_csv_rows(DATA / "fitting_costs.csv")}


def fitting_cost(fitting_type: str, dn: int, material: str = "CS") -> float:
    try:
        return _fitting_costs()[(fitting_type, int(dn), material)]
    except KeyError:
        raise KeyError(f"No cost for {fitting_type} DN{dn} {material}") from None


@lru_cache(maxsize=1)
def _valve_costs() -> dict[tuple[int, str, str], float]:
    return {(int(r["dn"]), r["material"], r["actuation"]): float(r["cost_usd"])
            for r in read_csv_rows(DATA / "valve_costs.csv")}


def valve_cost(dn: int, material: str = "CS", actuation: str = "pneumatic") -> float:
    """Cost of an actuated flanged valve [USD]."""
    try:
        return _valve_costs()[(int(dn), material, actuation)]
    except KeyError:
        raise KeyError(f"No valve cost for DN{dn} {material} {actuation}") from None
