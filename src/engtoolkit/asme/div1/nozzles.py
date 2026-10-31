"""
UG-37 reinforcement of a single opening by the area-replacement method (simplified).

Assumptions (state them in any report):
- one circular opening, nozzle set in (inserted through) the shell or head, axis normal to the surface;
- correction factor F = 1 (opening in a plane other than the longitudinal plane is not credited);
- the opening does not pass through a Category A weld unless E1 < 1 is entered;
- nozzle and pad strength reduction factors fr = Sn/Sv and Sp/Sv (capped at 1);
- weld areas use the outward fillet leg only (A41 nozzle-to-shell/pad, A42 pad-to-shell, leg² × fr);
- no check of weld strength (UG-41), nozzle neck minimum thickness (UG-45) or multiple-opening spacing (UG-42).

Required shell thickness tr follows UG-37(a): seamless shell (E = 1); for a 2:1 ellipsoidal head the
equivalent sphere radius K1·D with K1 = 0.9; for a torispherical head the seamless sphere of the crown
radius L; for a hemispherical head or sphere its own radius.

Preliminary sizing only: verify against the current edition of ASME BPVC VIII-1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from engtoolkit.core.results import Result, rfield

from .common import check_positive

HostKind = Literal["cylinder", "sphere", "ellipsoidal_2_1", "torispherical", "hemispherical"]

#: UG-36(c)(3): openings exempt from reinforcement calculations (finished opening diameter, host thickness).
SMALL_OPENING_ANY_T = 0.060      # 2 3/8 in in any thickness
SMALL_OPENING_THIN = 0.089       # 3 1/2 in in shells/heads ≤ 3/8 in thick
SMALL_OPENING_THIN_T = 0.010     # 3/8 in


def required_host_thickness(P: float, host: HostKind, D_inside: float, S: float, corrosion: float = 0.0,
                            crown_radius: float | None = None) -> float:
    """UG-37(a) tr: thickness of the seamless (E = 1) host under internal pressure, corroded."""
    D = D_inside + 2 * corrosion
    if host == "cylinder":
        return P * D / 2 / (S - 0.6 * P)
    if host in ("sphere", "hemispherical"):
        return P * D / 2 / (2 * S - 0.2 * P)
    if host == "ellipsoidal_2_1":
        return P * 0.9 * D / (2 * S - 0.2 * P)
    if host == "torispherical":
        L = (D_inside if crown_radius is None else crown_radius) + corrosion
        return P * L / (2 * S - 0.2 * P)
    raise ValueError(f"Unknown host {host!r}")


@dataclass
class NozzleResult(Result):
    status: str = rfield("", "Reinforcement")
    A_required: float = rfield("m^2", "Area required A")
    A_available: float = rfield("m^2", "Area available")
    margin: float = rfield("m^2", "Excess area (available − required)")
    A1: float = rfield("m^2", "A1 shell")
    A2: float = rfield("m^2", "A2 nozzle wall outward")
    A3: float = rfield("m^2", "A3 nozzle inward projection")
    A41: float = rfield("m^2", "A41 nozzle weld")
    A42: float = rfield("m^2", "A42 pad weld")
    A5: float = rfield("m^2", "A5 reinforcing pad")
    d: float = rfield("m", "Finished opening diameter d (corroded)")
    tr: float = rfield("m", "Required host thickness tr (E = 1)")
    trn: float = rfield("m", "Required nozzle thickness trn")
    t: float = rfield("m", "Host thickness t (corroded)")
    tn: float = rfield("m", "Nozzle wall tn (corroded)")
    limit_parallel: float = rfield("m", "Reinforcement limit parallel to wall (each side of axis)")
    limit_normal: float = rfield("m", "Reinforcement limit normal to wall (outward)")
    small_opening_exempt: bool = rfield("", "UG-36(c)(3) small opening (calculation not required)")
    clause: str = rfield("", "Clause", default="UG-37 (simplified, F = 1)")
    notes: list = rfield("", "Notes", default_factory=list, summary=False)


def nozzle_reinforcement(P: float, host: HostKind, D_host: float, t_host: float, S_host: float,
                         d_nozzle: float, t_nozzle: float, S_nozzle: float | None = None,
                         corrosion: float = 0.0, corrosion_nozzle: float | None = None, E1: float = 1.0,
                         pad_diameter: float = 0.0, pad_thickness: float = 0.0, S_pad: float | None = None,
                         weld_leg_nozzle: float = 0.0, weld_leg_pad: float = 0.0,
                         inward_projection: float = 0.0, crown_radius: float | None = None) -> NozzleResult:
    """
    UG-37 area check for a set-in nozzle with optional reinforcing pad (all dimensions new, in m).

    ``d_nozzle`` is the nozzle inside diameter, ``t_host`` and ``t_nozzle`` nominal wall thicknesses,
    ``pad_diameter`` the pad outside diameter (0 = no pad). Corrosion is removed from walls and added
    to the opening.
    """
    check_positive(P=P, D_host=D_host, t_host=t_host, S_host=S_host, d_nozzle=d_nozzle, t_nozzle=t_nozzle)
    cn = corrosion if corrosion_nozzle is None else corrosion_nozzle
    Sn = S_host if S_nozzle is None else S_nozzle
    Sp = Sn if S_pad is None else S_pad
    fr1 = fr2 = min(Sn / S_host, 1.0)
    fr3 = min(Sn, Sp) / S_host if pad_thickness > 0 else fr2
    fr3 = min(fr3, 1.0)
    fr4 = min(Sp / S_host, 1.0)
    F = 1.0

    d = d_nozzle + 2 * cn
    t = t_host - corrosion
    tn = t_nozzle - cn
    te = pad_thickness
    if t <= 0 or tn <= 0:
        raise ValueError("Wall thickness must exceed the corrosion allowance")
    tr = required_host_thickness(P, host, D_host, S_host, corrosion, crown_radius)
    Rn = d / 2
    trn = P * Rn / (Sn - 0.6 * P)

    A = d * tr * F + 2 * tn * tr * F * (1 - fr1)
    excess = E1 * t - F * tr
    A1 = max(d * excess, 2 * (t + tn) * excess) - 2 * tn * excess * (1 - fr1)
    A1 = max(A1, 0.0)
    if te > 0:
        A2 = min(5 * (tn - trn) * fr2 * t, 2 * (tn - trn) * (2.5 * tn + te) * fr2)
    else:
        A2 = min(5 * (tn - trn) * fr2 * t, 5 * (tn - trn) * fr2 * tn)
    A2 = max(A2, 0.0)
    ti = tn  # inward projection has the same wall; corrosion on both faces is ignored (conservative enough)
    h = inward_projection
    A3 = min(5 * t * ti * fr2, 5 * ti * ti * fr2, 2 * h * ti * fr2) if h > 0 else 0.0
    A41 = weld_leg_nozzle ** 2 * fr3
    A42 = weld_leg_pad ** 2 * fr4 if te > 0 else 0.0
    notes: list[str] = []
    if te > 0 and pad_diameter > 0:
        Dp = min(pad_diameter, 2 * d)
        if pad_diameter > 2 * d:
            notes.append("Pad extends beyond the 2d reinforcement limit; only the part inside it is credited")
        A5 = max((Dp - d - 2 * tn) * te * fr4, 0.0)
    else:
        A5 = 0.0
    available = A1 + A2 + A3 + A41 + A42 + A5

    exempt = d <= SMALL_OPENING_ANY_T or (d <= SMALL_OPENING_THIN and t_host <= SMALL_OPENING_THIN_T)
    if exempt:
        notes.append("UG-36(c)(3): opening small enough that reinforcement calculations are not required")
    if tn < trn:
        notes.append("Nozzle wall thinner than required for pressure (check UG-45)")
    if d > D_host / 2 and host == "cylinder":
        notes.append("Large opening (d > D/2): Appendix 1-7 rules may also apply")
    notes.append("Simplified: F = 1, set-in nozzle, outward fillet welds only; check UG-41 weld strength and UG-45")
    ok = available >= A * (1 - 1e-9) or exempt
    return NozzleResult(
        status="PASS" if ok else "FAIL", A_required=A, A_available=available, margin=available - A,
        A1=A1, A2=A2, A3=A3, A41=A41, A42=A42, A5=A5, d=d, tr=tr, trn=trn, t=t, tn=tn,
        limit_parallel=max(d, d / 2 + t + tn), limit_normal=min(2.5 * t, 2.5 * tn + te),
        small_opening_exempt=exempt, notes=notes,
    )
