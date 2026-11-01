"""
UG-27 shells under internal pressure: cylinders (circumferential and longitudinal stress) and spheres,
with the Mandatory Appendix 1-2 thick-wall formulas beyond the UG-27 limits.

All lengths in m, pressures and stresses in Pa. Dimensions are taken in the corroded condition:
inside radius R = R_new + CA and the required thickness is reported with CA added back.

Preliminary sizing only: verify against the current edition of ASME BPVC VIII-1. S is a user input
(Section II-D); no code tables are reproduced.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from engtoolkit.core.results import Result, rfield

from .common import UG16_MIN_THICKNESS, available_thickness, check_E, check_positive, next_plate


# ---------------- pure formulas (corroded inside radius R, thickness t without CA) ----------------

def cylinder_circumferential_t(P: float, R: float, S: float, E: float) -> tuple[float, str]:
    """UG-27(c)(1) t = PR/(SE − 0.6P); Appendix 1-2(a)(1) when P > 0.385SE or t > R/2."""
    if P <= 0.385 * S * E:
        t = P * R / (S * E - 0.6 * P)
        if t <= R / 2:
            return t, "UG-27(c)(1)"
    Z = (S * E + P) / (S * E - P) if S * E > P else math.inf
    return R * (math.sqrt(Z) - 1), "Appendix 1-2(a)(1)"


def cylinder_circumferential_P(t: float, R: float, S: float, E: float) -> float:
    P_thin = S * E * t / (R + 0.6 * t)
    if t <= R / 2 and P_thin <= 0.385 * S * E:
        return P_thin
    Z = ((R + t) / R) ** 2
    return S * E * (Z - 1) / (Z + 1)


def cylinder_longitudinal_t(P: float, R: float, S: float, E: float) -> tuple[float, str]:
    """UG-27(c)(2) t = PR/(2SE + 0.4P); Appendix 1-2(a)(2) when P > 1.25SE or t > R/2."""
    t = P * R / (2 * S * E + 0.4 * P)
    if P <= 1.25 * S * E and t <= R / 2:
        return t, "UG-27(c)(2)"
    return R * (math.sqrt(P / (S * E) + 1) - 1), "Appendix 1-2(a)(2)"


def cylinder_longitudinal_P(t: float, R: float, S: float, E: float) -> float:
    P_thin = 2 * S * E * t / (R - 0.4 * t)
    if t <= R / 2 and P_thin <= 1.25 * S * E:
        return P_thin
    return S * E * (((R + t) / R) ** 2 - 1)


def sphere_t(P: float, R: float, S: float, E: float) -> tuple[float, str]:
    """UG-27(d) t = PR/(2SE − 0.2P); Appendix 1-3 when P > 0.665SE or t > 0.356R."""
    if P <= 0.665 * S * E:
        t = P * R / (2 * S * E - 0.2 * P)
        if t <= 0.356 * R:
            return t, "UG-27(d)"
    Y = 2 * (S * E + P) / (2 * S * E - P) if 2 * S * E > P else math.inf
    return R * (Y ** (1 / 3) - 1), "Appendix 1-3"


def sphere_P(t: float, R: float, S: float, E: float) -> float:
    P_thin = 2 * S * E * t / (R + 0.2 * t)
    if t <= 0.356 * R and P_thin <= 0.665 * S * E:
        return P_thin
    Y = ((R + t) / R) ** 3
    return 2 * S * E * (Y - 1) / (Y + 2)


# ---------------- results ----------------

@dataclass
class ShellResult(Result):
    t_required: float = rfield("m", "Required thickness incl. CA")
    t_pressure: float = rfield("m", "Pressure thickness (governing)")
    t_nominal: float = rfield("m", "Nominal thickness")
    mawp: float = rfield("Pa", "MAWP at nominal thickness (corroded)")
    governing: str = rfield("", "Governing case")
    clause: str = rfield("", "Clause")
    status: str = rfield("", "Status")
    t_circumferential: float = rfield("m", "t from circumferential stress")
    t_longitudinal: float = rfield("m", "t from longitudinal stress")
    mawp_circumferential: float = rfield("Pa", "MAWP, circumferential stress")
    mawp_longitudinal: float = rfield("Pa", "MAWP, longitudinal stress")
    R_corroded: float = rfield("m", "Inside radius (corroded)")
    utilisation: float = rfield("", "Design pressure / MAWP")
    notes: list = rfield("", "Notes", default_factory=list, summary=False)


def _finish(t_press, t_nom, corrosion, undertolerance, mawp_fn, ug16_min):
    t_min = max(t_press, ug16_min)
    t_required = t_min + corrosion + undertolerance
    t_nominal = t_nom if t_nom is not None else next_plate(t_required)
    t_avail = available_thickness(t_nominal, corrosion, undertolerance)
    return t_required, t_nominal, mawp_fn(t_avail)


def cylindrical_shell(P: float, D_inside: float, S: float, E: float = 1.0, corrosion: float = 0.0,
                      t_nominal: float | None = None, E_circ: float | None = None, undertolerance: float = 0.0,
                      ug16_min: float = UG16_MIN_THICKNESS) -> ShellResult:
    """
    UG-27(c) cylindrical shell under internal pressure P.

    E is the efficiency of the longitudinal (Category A) joints and governs the circumferential stress;
    ``E_circ`` (default E) is the efficiency of the circumferential joints, governing longitudinal stress.
    With ``t_nominal=None`` the next standard plate above the required thickness is chosen.
    """
    check_positive(P=P, D_inside=D_inside, S=S)
    check_E(E)
    E_circ = E if E_circ is None else E_circ
    check_E(E_circ)
    R = D_inside / 2 + corrosion
    t_c, clause_c = cylinder_circumferential_t(P, R, S, E)
    t_l, clause_l = cylinder_longitudinal_t(P, R, S, E_circ)
    circ = t_c >= t_l
    t_press = t_c if circ else t_l

    def mawp(t):
        return min(cylinder_circumferential_P(t, R, S, E), cylinder_longitudinal_P(t, R, S, E_circ))

    t_required, t_nom, P_max = _finish(t_press, t_nominal, corrosion, undertolerance, mawp, ug16_min)
    t_avail = available_thickness(t_nom, corrosion, undertolerance)
    notes = []
    if t_press < ug16_min:
        notes.append(f"UG-16(b) minimum {ug16_min * 1e3:.1f} mm governs over the pressure thickness")
    if "Appendix" in clause_c:
        notes.append("Thick wall: P > 0.385SE or t > R/2, Appendix 1-2 formula used")
    return ShellResult(
        t_required=t_required, t_pressure=t_press, t_nominal=t_nom, mawp=P_max,
        governing="circumferential stress" if circ else "longitudinal stress",
        clause=clause_c if circ else clause_l, status="PASS" if P_max >= P * (1 - 1e-9) else "FAIL",
        t_circumferential=t_c, t_longitudinal=t_l,
        mawp_circumferential=cylinder_circumferential_P(t_avail, R, S, E),
        mawp_longitudinal=cylinder_longitudinal_P(t_avail, R, S, E_circ),
        R_corroded=R, utilisation=P / P_max, notes=notes,
    )


def spherical_shell(P: float, D_inside: float, S: float, E: float = 1.0, corrosion: float = 0.0,
                    t_nominal: float | None = None, undertolerance: float = 0.0,
                    ug16_min: float = UG16_MIN_THICKNESS) -> ShellResult:
    """UG-27(d) spherical shell under internal pressure (Appendix 1-3 when thick)."""
    check_positive(P=P, D_inside=D_inside, S=S)
    check_E(E)
    R = D_inside / 2 + corrosion
    t_press, clause = sphere_t(P, R, S, E)
    t_required, t_nom, P_max = _finish(t_press, t_nominal, corrosion, undertolerance,
                                       lambda t: sphere_P(t, R, S, E), ug16_min)
    notes = []
    if t_press < ug16_min:
        notes.append(f"UG-16(b) minimum {ug16_min * 1e3:.1f} mm governs over the pressure thickness")
    if "Appendix" in clause:
        notes.append("Thick wall: P > 0.665SE or t > 0.356R, Appendix 1-3 formula used")
    return ShellResult(
        t_required=t_required, t_pressure=t_press, t_nominal=t_nom, mawp=P_max, governing="membrane stress",
        clause=clause, status="PASS" if P_max >= P * (1 - 1e-9) else "FAIL",
        t_circumferential=t_press, t_longitudinal=t_press, mawp_circumferential=P_max, mawp_longitudinal=P_max,
        R_corroded=R, utilisation=P / P_max, notes=notes,
    )
