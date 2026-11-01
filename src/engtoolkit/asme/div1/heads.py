"""
UG-32 formed heads (pressure on the concave side) and UG-34 unstayed flat heads.

Formed heads: 2:1 ellipsoidal (UG-32(c)), general ellipsoidal (Appendix 1-4(c), factor K),
torispherical with 6 % knuckle (UG-32(d)) or any knuckle (Appendix 1-4(d), factor M) and
hemispherical (UG-32(f), Appendix 1-3 when thick). Flat heads use UG-34 with the attachment factor C
chosen by the user from the sketches of Fig. UG-34.

All dimensions are inside dimensions of the new head in m; corrosion is added to them internally.
Seamless heads use E = 1; use the Category A joint efficiency for heads made from welded plates.

Preliminary sizing only: verify against the current edition of ASME BPVC VIII-1. S is a user input
(Section II-D); no code tables are reproduced.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from engtoolkit.core.results import Result, rfield

from .common import UG16_MIN_THICKNESS, available_thickness, check_E, check_positive, next_plate
from .shells import sphere_P, sphere_t

HeadKind = Literal["ellipsoidal_2_1", "ellipsoidal", "torispherical", "hemispherical", "flat"]

#: Typical UG-34 attachment factors C (check the actual sketch in Fig. UG-34 before use).
FLAT_HEAD_C = {
    0.17: "Forged or flanged head integral with shell, knuckle radius ≥ 3t (sketch (a))",
    0.20: "Integral flanged/forged head with taper or lap joint (sketches (b-1), (c))",
    0.25: "Bolted or threaded cover, circular (sketches (j), (k) with gasket moment term)",
    0.30: "Bolted flat cover with gasket (sketches (j), (k)); include W and h_G",
    0.33: "Plate welded inside shell, m = 1 (sketches (e), (f), (g))",
}
FLAT_HEAD_C_CHOICES = tuple(FLAT_HEAD_C)


def ellipsoid_K(ratio: float) -> float:
    """Appendix 1-4(c) factor K = (2 + (D/2h)²)/6 for an ellipsoidal head with axis ratio D/2h."""
    return (2 + ratio ** 2) / 6


def torisphere_M(L: float, r: float) -> float:
    """Appendix 1-4(d) factor M = (3 + √(L/r))/4."""
    return (3 + math.sqrt(L / r)) / 4


def head_depth(kind: HeadKind, D: float, ratio: float = 2.0, L: float | None = None, r: float | None = None) -> float:
    """Inside depth of a head [m] (crown to tangent line)."""
    if kind == "ellipsoidal_2_1":
        return D / 4
    if kind == "ellipsoidal":
        return D / (2 * ratio)
    if kind == "hemispherical":
        return D / 2
    if kind == "torispherical":
        L = D if L is None else L
        r = 0.06 * L if r is None else r
        return L - math.sqrt((L - r) ** 2 - (D / 2 - r) ** 2)
    return 0.0


@dataclass
class HeadResult(Result):
    kind: str = rfield("", "Head type")
    t_required: float = rfield("m", "Required thickness incl. CA (after forming)")
    t_pressure: float = rfield("m", "Pressure thickness")
    t_nominal: float = rfield("m", "Nominal thickness")
    mawp: float = rfield("Pa", "MAWP at nominal thickness (corroded)")
    clause: str = rfield("", "Clause")
    status: str = rfield("", "Status")
    factor: float = rfield("", "Shape factor (K, M or C)")
    depth: float = rfield("m", "Inside depth of head")
    utilisation: float = rfield("", "Design pressure / MAWP")
    notes: list = rfield("", "Notes", default_factory=list, summary=False)


def formed_head(P: float, D_inside: float, S: float, kind: HeadKind = "ellipsoidal_2_1", E: float = 1.0,
                corrosion: float = 0.0, t_nominal: float | None = None, ratio: float = 2.0,
                crown_radius: float | None = None, knuckle_radius: float | None = None,
                undertolerance: float = 0.0, ug16_min: float = UG16_MIN_THICKNESS) -> HeadResult:
    """
    Required thickness and MAWP of a formed head under internal pressure (pressure on concave side).

    ``ratio`` is D/2h for the general ellipsoidal head. ``crown_radius`` L and ``knuckle_radius`` r are
    inside radii of a torispherical head (default L = D, r = 0.06 L: the UG-32(d) head). The thickness
    is the minimum after forming; order extra plate for thinning.
    """
    check_positive(P=P, D_inside=D_inside, S=S)
    check_E(E)
    if kind == "flat":
        raise ValueError("Use flat_head() for UG-34 flat heads")
    c = corrosion
    D = D_inside + 2 * c
    notes: list[str] = []
    depth = head_depth(kind, D_inside, ratio, crown_radius, knuckle_radius)

    if kind == "ellipsoidal_2_1":
        K = 1.0
        t_p = P * D / (2 * S * E - 0.2 * P)
        mawp = lambda t: 2 * S * E * t / (D + 0.2 * t)
        clause = "UG-32(c)"
    elif kind == "ellipsoidal":
        if not 1.0 <= ratio <= 3.0:
            raise ValueError("Appendix 1-4(c) covers ellipsoidal heads with 1.0 ≤ D/2h ≤ 3.0")
        K = ellipsoid_K(ratio)
        t_p = P * D * K / (2 * S * E - 0.2 * P)
        mawp = lambda t: 2 * S * E * t / (K * D + 0.2 * t)
        clause = "Appendix 1-4(c)"
    elif kind == "torispherical":
        L0 = D_inside if crown_radius is None else crown_radius
        r0 = 0.06 * L0 if knuckle_radius is None else knuckle_radius
        check_positive(crown_radius=L0, knuckle_radius=r0)
        L, r = L0 + c, r0 + c
        if L0 > D_inside * 1.0 + 1e-12:
            notes.append("Crown radius exceeds the head diameter: UG-32(j) limits L to the skirt outside diameter")
        if L / r > 50 / 3:
            raise ValueError("Appendix 1-4(d) requires L/r ≤ 16⅔ (knuckle at least 6 % of crown radius)")
        K = torisphere_M(L, r)
        if abs(r0 / L0 - 0.06) < 1e-9:
            t_p = 0.885 * P * L / (S * E - 0.1 * P)
            mawp = lambda t: S * E * t / (0.885 * L + 0.1 * t)
            clause = "UG-32(d) (6 % knuckle)"
        else:
            t_p = P * L * K / (2 * S * E - 0.2 * P)
            mawp = lambda t: 2 * S * E * t / (L * K + 0.2 * t)
            clause = "Appendix 1-4(d)"
    elif kind == "hemispherical":
        K = 1.0
        L = D / 2
        t_p, clause = sphere_t(P, L, S, E)
        clause = "UG-32(f)" if clause == "UG-27(d)" else clause
        mawp = lambda t: sphere_P(t, L, S, E)
    else:
        raise ValueError(f"Unknown head kind {kind!r}")

    if t_p <= 0 or not math.isfinite(t_p):
        raise ValueError("Design pressure too high for this head and allowable stress")
    t_min = max(t_p, ug16_min)
    if t_p < ug16_min:
        notes.append(f"UG-16(b) minimum {ug16_min * 1e3:.1f} mm governs over the pressure thickness")
    t_required = t_min + c + undertolerance
    t_nom = t_nominal if t_nominal is not None else next_plate(t_required)
    t_avail = available_thickness(t_nom, c, undertolerance)
    if kind == "torispherical" and knuckle_radius is not None and knuckle_radius < 3 * t_nom:
        notes.append("UG-32(j): knuckle radius should be at least 3 × head thickness")
    if kind == "torispherical" and t_avail / (crown_radius or D_inside) < 0.002:
        notes.append("t/L < 0.002: Appendix 1-4(f) rules for thin torispherical heads also apply")
    P_max = mawp(t_avail)
    return HeadResult(kind, t_required, t_p, t_nom, P_max, clause, "PASS" if P_max >= P * (1 - 1e-9) else "FAIL",
                      K, depth, P / P_max, notes)


def flat_head(P: float, d: float, S: float, C: float = 0.33, E: float = 1.0, corrosion: float = 0.0,
              t_nominal: float | None = None, W: float = 0.0, h_G: float = 0.0,
              undertolerance: float = 0.0, ug16_min: float = UG16_MIN_THICKNESS) -> HeadResult:
    """
    UG-34 circular unstayed flat head or cover: t = d·√(CP/SE + 1.9·W·h_G/(S·E·d³)).

    ``d`` is the diameter (new) measured as shown in Fig. UG-34, ``C`` the attachment factor of the
    chosen sketch, ``W`` the bolt load and ``h_G`` the gasket moment arm for bolted covers (eq. (2)).
    """
    check_positive(P=P, d=d, S=S, C=C)
    check_E(E)
    dc = d + 2 * corrosion
    bolt = 1.9 * W * h_G / (S * E * dc ** 3)
    t_p = dc * math.sqrt(C * P / (S * E) + bolt)
    notes = [f"C = {C:g}: {FLAT_HEAD_C.get(C, 'user-defined attachment factor')}"]
    if t_p < ug16_min:
        notes.append(f"UG-16(b) minimum {ug16_min * 1e3:.1f} mm governs over the pressure thickness")
    t_required = max(t_p, ug16_min) + corrosion + undertolerance
    t_nom = t_nominal if t_nominal is not None else next_plate(t_required)
    t_avail = available_thickness(t_nom, corrosion, undertolerance)
    P_max = (S * E * (t_avail / dc) ** 2 - 1.9 * W * h_G / dc ** 3) / C
    clause = "UG-34 eq. (2)" if W > 0 else "UG-34 eq. (1)"
    return HeadResult("flat", t_required, t_p, t_nom, P_max, clause, "PASS" if P_max >= P * (1 - 1e-9) else "FAIL",
                      C, 0.0, P / P_max if P_max > 0 else math.inf, notes)
