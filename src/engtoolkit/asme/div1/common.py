"""
Shared Division 1 helpers: joint efficiency options, UG-16 minimum thickness, standard plate
thicknesses, corrosion handling and the UG-99(b) hydrostatic test pressure.

Preliminary sizing only: verify every result against the current edition of ASME BPVC Section VIII
Division 1. No code tables are reproduced; allowable stresses S are user inputs (Section II-D).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from engtoolkit.core.results import Result, rfield

DISCLAIMER = ("Preliminary sizing to ASME BPVC VIII-1 equations. Verify against the current code edition; "
              "allowable stresses (Section II-D) and chart factors are user inputs, no code tables are reproduced.")

#: UG-16(b): minimum thickness of shells and heads, exclusive of corrosion allowance (1/16 in).
UG16_MIN_THICKNESS = 1.5e-3

#: Typical joint efficiencies for Category A butt joints (UW-12). Value -> note.
JOINT_EFFICIENCIES = {
    1.0: "Type 1 double-welded butt, full radiography (UW-11(a)); or seamless",
    0.85: "Type 1 double-welded butt, spot radiography (UW-11(b))",
    0.70: "Type 1 double-welded butt, no radiography",
    0.90: "Type 2 single-welded with backing strip, full radiography",
    0.80: "Type 2 single-welded with backing strip, spot radiography",
    0.65: "Type 2 single-welded with backing strip, no radiography",
}
JOINT_EFFICIENCY_CHOICES = tuple(JOINT_EFFICIENCIES)

#: Commonly stocked plate thicknesses [m] used to round a required thickness up to a nominal plate.
STANDARD_PLATES = tuple(t * 1e-3 for t in (3, 4, 5, 6, 8, 10, 12, 14, 15, 16, 18, 20, 22, 25, 28, 30, 32, 35,
                                           38, 40, 45, 50, 55, 60, 65, 70, 75, 80, 90, 100, 110, 120, 130, 150))


def next_plate(t_required: float) -> float:
    """Smallest standard plate thickness ≥ ``t_required`` [m] (whole millimetres beyond the list)."""
    for t in STANDARD_PLATES:
        if t >= t_required - 1e-9:
            return t
    return math.ceil(t_required * 1e3) * 1e-3


def check_positive(**values: float) -> None:
    for name, v in values.items():
        if not v > 0:
            raise ValueError(f"{name} must be positive (got {v})")


def check_E(E: float) -> None:
    if not 0 < E <= 1:
        raise ValueError(f"Joint efficiency E must be in (0, 1] (got {E})")


def available_thickness(t_nominal: float, corrosion: float, undertolerance: float = 0.0) -> float:
    """Thickness that resists pressure: nominal minus corrosion allowance and mill undertolerance."""
    t = t_nominal - corrosion - undertolerance
    if t <= 0:
        raise ValueError("Nominal thickness must exceed corrosion allowance plus undertolerance")
    return t


# ---------------- UG-99(b) hydrostatic test ----------------

@dataclass
class HydrotestResult(Result):
    test_pressure: float = rfield("Pa", "Hydrostatic test pressure (UG-99(b))")
    stress_ratio: float = rfield("", "Stress ratio S_test / S_design (LSR)")
    basis_pressure: float = rfield("Pa", "Basis pressure (MAWP or design pressure)")
    clause: str = rfield("", "Clause", default="UG-99(b): 1.3 × MAWP × LSR")


def hydrotest_pressure(mawp: float, S_test: float, S_design: float) -> HydrotestResult:
    """
    UG-99(b) minimum hydrostatic test pressure 1.3 × MAWP × (S at test temperature / S at design
    temperature). Use the lowest stress ratio (LSR) of the pressure-retaining materials. The result is
    measured at the top of the vessel; add static head for the lower parts.
    """
    check_positive(mawp=mawp, S_test=S_test, S_design=S_design)
    ratio = S_test / S_design
    return HydrotestResult(1.3 * mawp * ratio, ratio, mawp)
