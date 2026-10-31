"""
Vapour-compression refrigeration / heat-pump cycle (SI units, temperatures in K).

States: 1 compressor inlet (evaporator exit), 2 compressor outlet, 3 condenser exit,
4 evaporator inlet (after throttling). Compression uses an isentropic efficiency.
Reference: Cengel & Boles, *Thermodynamics*, ch. 11.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from engtoolkit.materials._coolprop import CP

from engtoolkit.core.results import Result, rfield


@dataclass
class CycleState(Result):
    label: str = rfield("", "State")
    T: float = rfield("K", "Temperature")
    P: float = rfield("Pa", "Pressure")
    h: float = rfield("J/kg", "Enthalpy")
    s: float = rfield("J/(kg·K)", "Entropy")
    Q: float = rfield("", "Quality", default=math.nan)


@dataclass
class RefrigerationCycleResult(Result):
    refrigerant: str = rfield("", "Refrigerant")
    COP_cooling: float = rfield("", "COP (cooling)")
    COP_heating: float = rfield("", "COP (heating)")
    mass_flow: float = rfield("kg/s", "Refrigerant mass flow")
    cooling_load: float = rfield("W", "Cooling capacity")
    heating_load: float = rfield("W", "Heating capacity")
    compressor_power: float = rfield("W", "Compressor power")
    P_evaporator: float = rfield("Pa", "Evaporator pressure")
    P_condenser: float = rfield("Pa", "Condenser pressure")
    pressure_ratio: float = rfield("", "Pressure ratio")
    T_discharge: float = rfield("K", "Compressor discharge temperature")
    temperature_lift: float = rfield("ΔK", "Temperature lift")
    states: list = rfield("", "Cycle states", default_factory=list, summary=False)


def _state(label: str, name: str, **inputs) -> CycleState:
    (k1, v1), (k2, v2) = inputs.items()
    get = lambda key: CP.PropsSI(key, k1, v1, k2, v2, name)
    try:
        Q = get("Q")
        Q = Q if 0 <= Q <= 1 else math.nan
    except ValueError:
        Q = math.nan
    return CycleState(label, get("T"), get("P"), get("H"), get("S"), Q)


def refrigeration_cycle(refrigerant: str, T_evap: float, T_cond: float, compressor_power: float,
                        isentropic_efficiency: float = 0.75, superheat: float = 0.0,
                        subcooling: float = 0.0) -> RefrigerationCycleResult:
    """
    Single-stage vapour-compression cycle.

    T_evap, T_cond: saturation temperatures [K]; compressor_power: shaft power [W];
    superheat / subcooling: [K] at evaporator / condenser exit.
    """
    if not 0 < isentropic_efficiency <= 1:
        raise ValueError("Isentropic efficiency must be in (0, 1]")
    if T_cond <= T_evap:
        raise ValueError("Condensing temperature must be above evaporating temperature")
    try:
        P_ev = CP.PropsSI("P", "T", T_evap, "Q", 1, refrigerant)
        P_co = CP.PropsSI("P", "T", T_cond, "Q", 0, refrigerant)
        s1 = (_state("1", refrigerant, P=P_ev, Q=1) if superheat == 0
              else _state("1", refrigerant, P=P_ev, T=T_evap + superheat))
        s2s_h = CP.PropsSI("H", "P", P_co, "S", s1.s, refrigerant)
        h2 = s1.h + (s2s_h - s1.h) / isentropic_efficiency
        s2 = _state("2", refrigerant, P=P_co, H=h2)
        s3 = (_state("3", refrigerant, P=P_co, Q=0) if subcooling == 0
              else _state("3", refrigerant, P=P_co, T=T_cond - subcooling))
        s4 = _state("4", refrigerant, P=P_ev, H=s3.h)
    except ValueError as err:
        raise ValueError(
            f"Cycle for {refrigerant} not solvable at T_evap={T_evap - 273.15:.1f} °C, "
            f"T_cond={T_cond - 273.15:.1f} °C: {err}") from err

    w = s2.h - s1.h
    q_evap = s1.h - s4.h
    q_cond = s2.h - s3.h
    m = compressor_power / w
    return RefrigerationCycleResult(
        refrigerant=refrigerant, COP_cooling=q_evap / w, COP_heating=q_cond / w, mass_flow=m,
        cooling_load=m * q_evap, heating_load=m * q_cond, compressor_power=compressor_power,
        P_evaporator=P_ev, P_condenser=P_co, pressure_ratio=P_co / P_ev, T_discharge=s2.T,
        temperature_lift=T_cond - T_evap, states=[s1, s2, s3, s4],
    )


def refrigerant_info(refrigerant: str) -> dict[str, float]:
    """Environmental (GWP100, GWP20, ODP) and hazard (HH, FH, PH) ratings; NaN where CoolProp has none."""
    out = {}
    for key in ("GWP100", "GWP20", "ODP", "HH", "FH", "PH"):
        try:
            value = CP.PropsSI(key, refrigerant)
            out[key] = value if value > -1e20 else math.nan
        except ValueError:
            out[key] = math.nan
    return out
