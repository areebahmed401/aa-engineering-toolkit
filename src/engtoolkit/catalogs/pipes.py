"""Standard pipe sizes (ASME B36.10M/B36.19M), weights and supplier costs."""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from engtoolkit.core.data import read_csv_rows

DATA = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class PipeSize:
    dn: int
    nps: str
    schedule: str
    od: float    # outside diameter [m]
    wall: float  # wall thickness [m]

    @property
    def id(self) -> float:
        """Inside diameter [m]."""
        return self.od - 2 * self.wall

    @property
    def flow_area(self) -> float:
        return math.pi * self.id**2 / 4

    @property
    def metal_area(self) -> float:
        return math.pi / 4 * (self.od**2 - self.id**2)

    def mass_per_m(self, rho: float = 7850.0) -> float:
        """Pipe mass per metre [kg/m] for a wall material of density rho."""
        return self.metal_area * rho

    @property
    def label(self) -> str:
        return f"DN{self.dn} (NPS {self.nps}) Sch {self.schedule}"


@lru_cache(maxsize=1)
def _sizes() -> dict[tuple[int, str], PipeSize]:
    out = {}
    for row in read_csv_rows(DATA / "pipe_schedules.csv"):
        size = PipeSize(int(row["dn"]), row["nps"], row["schedule"],
                        float(row["od_mm"]) / 1000, float(row["wall_mm"]) / 1000)
        out[(size.dn, size.schedule)] = size
    return out


def schedules() -> list[str]:
    return sorted({s for _, s in _sizes()}, key=float)


def sizes(schedule: str = "40") -> list[PipeSize]:
    """All sizes available in a schedule, smallest first."""
    return sorted((p for (dn, s), p in _sizes().items() if s == str(schedule)), key=lambda p: p.dn)


def pipe(dn: int, schedule: str = "40") -> PipeSize:
    try:
        return _sizes()[(int(dn), str(schedule))]
    except KeyError:
        raise KeyError(f"No DN{dn} in schedule {schedule}. Available: {[p.dn for p in sizes(schedule)]}") from None


@lru_cache(maxsize=1)
def _costs() -> dict[int, float]:
    return {int(r["dn"]): float(r["usd_per_m"]) for r in read_csv_rows(DATA / "pipe_costs.csv")}


def cost_per_m(dn: int) -> float:
    """Supplier cost of Sch 40 carbon steel pipe [USD/m] (see data/pipe_costs.csv)."""
    try:
        return _costs()[int(dn)]
    except KeyError:
        raise KeyError(f"No cost data for DN{dn}") from None
