"""
UG-28 cylindrical shells under external pressure.

UG-28(c) needs factor A from Fig. G and factor B from the material chart of Section II-D Subpart 3.
**Neither chart is reproduced here.** Factor A is estimated from the elastic buckling strain that
Fig. G is built on (Windenburg & Trilling short-cylinder formula, bounded below by the long-cylinder
limit A = 1.1/(Do/t)²); you can override it with the value read from Fig. G. Factor B must be read
by the user from the applicable material chart. Without B, the elastic-region formula
Pa = 2AE/(3·Do/t) is used, which is only valid when A falls to the left of the material curve.

Preliminary sizing only: verify against the current edition of ASME BPVC VIII-1.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from engtoolkit.core.results import Result, rfield
from engtoolkit.core.solvers import brentq

from .common import check_positive

NU = 0.3


def factor_A(L: float, Do: float, t: float, nu: float = NU) -> float:
    """
    Approximate UG-28 factor A (elastic hoop strain at buckling, not a Fig. G reading).

    Short cylinders: Windenburg-Trilling P_cr = 2.42E(t/Do)^2.5 / ((1-ν²)^0.75 (L/Do - 0.45√(t/Do))).
    Long cylinders: P_cr = 2E/(1-ν²)·(t/Do)³. A = P_cr·Do/(2Et); L/Do is capped at 50 as in Fig. G.
    """
    check_positive(L=L, Do=Do, t=t)
    LD = min(L / Do, 50.0)
    td = t / Do
    long = 2 / (1 - nu ** 2) * td ** 3
    denom = LD - 0.45 * math.sqrt(td)
    short = 2.42 * td ** 2.5 / ((1 - nu ** 2) ** 0.75 * denom) if denom > 0 else math.inf
    A = max(long, short) / (2 * td)
    return min(A, 0.1)


@dataclass
class ExternalPressureResult(Result):
    status: str = rfield("", "Status")
    P_allowable: float = rfield("Pa", "Allowable external pressure Pa")
    method: str = rfield("", "Method")
    A: float = rfield("", "Factor A")
    A_source: str = rfield("", "Factor A source")
    B: float | None = rfield("Pa", "Factor B (user, from II-D chart)", default=None)
    P_elastic: float = rfield("Pa", "Pa if elastic, 2AE/(3·Do/t)", default=math.nan)
    L_over_Do: float = rfield("", "L/Do", default=math.nan)
    Do_over_t: float = rfield("", "Do/t", default=math.nan)
    t: float = rfield("m", "Thickness used (corroded)", default=math.nan)
    t_required_elastic: float = rfield("m", "Required t incl. CA (elastic region)", default=math.nan)
    utilisation: float = rfield("", "External pressure / Pa", default=math.nan)
    clause: str = rfield("", "Clause", default="UG-28(c)")
    notes: list = rfield("", "Notes", default_factory=list, summary=False)


def _pa(Do_t: float, A: float, B: float | None, E: float, S: float | None) -> tuple[float, str]:
    if Do_t >= 10:
        if B is None:
            return 2 * A * E / (3 * Do_t), "UG-28(c)(1) step 7 (elastic, B not supplied)"
        return 4 * B / (3 * Do_t), "UG-28(c)(1) step 6 (factor B)"
    if B is None or S is None:
        raise ValueError("Do/t < 10: UG-28(c)(2) needs factor B and the allowable stress S")
    pa1 = (2.167 / Do_t - 0.0833) * B
    pa2 = 2 * S / Do_t * (1 - 1 / Do_t)
    return min(pa1, pa2), "UG-28(c)(2)"


def external_pressure_cylinder(P_ext: float, Do: float, L: float, t_nominal: float, E_modulus: float,
                               B: float | None = None, A: float | None = None, corrosion: float = 0.0,
                               S: float | None = None) -> ExternalPressureResult:
    """
    Allowable external pressure of a cylinder (outside diameter Do, unsupported length L, nominal wall
    t_nominal) per UG-28(c). ``E_modulus`` is the elastic modulus at design temperature. Supply ``B``
    from the Section II-D material chart for the plastic region; ``A`` overrides the estimated factor.
    """
    check_positive(Do=Do, L=L, t_nominal=t_nominal, E_modulus=E_modulus)
    t = t_nominal - corrosion
    if t <= 0:
        raise ValueError("Nominal thickness must exceed the corrosion allowance")
    Do_t = Do / t
    notes: list[str] = []
    if Do_t < 4:
        A_val, source = 1.1 / Do_t ** 2, "UG-28(c)(2): A = 1.1/(Do/t)² for Do/t < 4"
    elif A is not None:
        A_val, source = A, "user (Fig. G)"
    else:
        A_val, source = factor_A(L, Do, t), "estimated (elastic buckling), verify with Fig. G"
    Pa, method = _pa(Do_t, A_val, B, E_modulus, S)
    P_el = 2 * A_val * E_modulus / (3 * Do_t)
    if B is not None and B > A_val * E_modulus / 2 * (1 + 1e-6):
        notes.append("B exceeds AE/2: B read from the chart should not exceed the elastic value")
    if B is None:
        notes.append("Factor B not supplied: elastic formula used; valid only if A lies left of the material line")
    notes.append("Section II-D Fig. G and material charts are not reproduced; read A and B from the code")

    t_req = math.nan
    if B is None and A is None and Do_t >= 10 and P_ext > 0:
        f = lambda tt: 2 * factor_A(L, Do, tt) * E_modulus / (3 * Do / tt) - P_ext
        if f(Do / 10) > 0:
            t_req = brentq(f, 1e-6 * Do, Do / 10) + corrosion
    return ExternalPressureResult(
        status=("PASS" if Pa >= P_ext * (1 - 1e-9) else "FAIL") if P_ext > 0 else "n/a",
        P_allowable=Pa, method=method, A=A_val, A_source=source, B=B, P_elastic=P_el,
        L_over_Do=L / Do, Do_over_t=Do_t, t=t, t_required_elastic=t_req,
        utilisation=P_ext / Pa if Pa > 0 else math.inf, notes=notes,
    )
