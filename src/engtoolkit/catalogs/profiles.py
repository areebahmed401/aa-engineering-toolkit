"""Standard rolled steel profiles (dimensions only; the structural package builds sections from them)."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from engtoolkit.core.data import read_csv_rows

DATA = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class IProfile:
    designation: str
    h: float   # overall depth [m]
    b: float   # flange width [m]
    tw: float  # web thickness [m]
    tf: float  # flange thickness [m]
    r: float   # root radius [m]

    @property
    def web_height(self) -> float:
        """Clear web height between flanges [m]."""
        return self.h - 2 * self.tf


def _norm(name: str) -> str:
    return name.upper().replace(" ", "")


@lru_cache(maxsize=1)
def _profiles() -> dict[str, IProfile]:
    out = {}
    for path in sorted(DATA.glob("*_profiles.csv")):
        for r in read_csv_rows(path):
            p = IProfile(r["designation"], *(float(r[k]) / 1000 for k in ("h_mm", "b_mm", "tw_mm", "tf_mm", "r_mm")))
            out[_norm(p.designation)] = p
    return out


def list_profiles(prefix: str | None = None) -> list[str]:
    names = [p.designation for p in _profiles().values()]
    return [n for n in names if prefix is None or n.upper().startswith(prefix.upper())]


def get_profile(designation: str) -> IProfile:
    """Profile by designation, e.g. 'IPE 200' (spaces and case ignored)."""
    try:
        return _profiles()[_norm(designation)]
    except KeyError:
        raise KeyError(f"Unknown profile {designation!r}. Available: {list_profiles()}") from None
