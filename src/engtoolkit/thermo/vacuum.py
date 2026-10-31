"""Vacuum pump sizing: pump-down and continuous gas load (SI units, temperatures in K)."""
from __future__ import annotations

import math
from dataclasses import dataclass

from engtoolkit.core.results import Result, rfield
from engtoolkit.materials import fluid

R_UNIVERSAL = 8.314462618
P_NORMAL, T_NORMAL = 101325.0, 273.15


def _mole_fractions(fluids: list[str], mass_fracs: list[float]) -> list[float]:
    total = sum(mass_fracs)
    if total <= 0:
        raise ValueError("Mass fractions cannot all be zero")
    moles = [mf / total / fluid(f).molar_mass for f, mf in zip(fluids, mass_fracs)]
    return [n / sum(moles) for n in moles]


def mixture_molar_mass(fluids: list[str], mass_fracs: list[float]) -> float:
    """Average molar mass [kg/mol] from mass fractions."""
    total = sum(mass_fracs)
    return total / sum(mf / fluid(f).molar_mass for f, mf in zip(fluids, mass_fracs))


def mixture_properties(fluids: list[str], mass_fracs: list[float], T: float, P: float) -> tuple[float, float]:
    """Approximate gas mixture density [kg/m³] and viscosity [Pa·s] (mole-fraction weighted)."""
    y = _mole_fractions(fluids, mass_fracs)
    states = [fluid(f).state(T=T, P=P) for f in fluids]
    return sum(yi * s.rho for yi, s in zip(y, states)), sum(yi * s.mu for yi, s in zip(y, states))


def _check_superheated(T: float, P: float) -> None:
    T_sat = fluid("Water").prop("T", P=P, Q=0)
    if T <= T_sat:
        raise ValueError(f"Water must be superheated: at {P / 100:.1f} mbar Tsat = {T_sat - 273.15:.2f} °C, "
                         f"given {T - 273.15:.2f} °C")


@dataclass
class PumpdownResult(Result):
    pump_speed: float = rfield("m^3/s", "Required pump speed (actual)")
    pump_speed_normal: float = rfield("m^3/s", "Pump speed at normal conditions")
    molar_mass: float = rfield("kg/mol", "Mixture molar mass")
    density: float = rfield("kg/m^3", "Density at initial pressure")
    viscosity: float = rfield("Pa·s", "Viscosity at initial pressure")


def pumpdown(volume: float, P_initial: float, P_final: float, time: float, T: float,
             fluids: list[str] = ("Air",), mass_fracs: list[float] = (1.0,)) -> PumpdownResult:
    """Pump speed to evacuate ``volume`` [m³] from P_initial to P_final [Pa] in ``time`` [s]: S = V/t·ln(Pi/Pf)."""
    if P_final >= P_initial:
        raise ValueError("Final pressure must be less than initial pressure")
    fluids, mass_fracs = list(fluids), list(mass_fracs)
    if "Water" in fluids:
        _check_superheated(T, P_initial)
    S = volume / time * math.log(P_initial / P_final)
    rho, mu = mixture_properties(fluids, mass_fracs, T, P_initial)
    return PumpdownResult(S, S * (P_initial / P_NORMAL) * (T_NORMAL / T),
                          mixture_molar_mass(fluids, mass_fracs), rho, mu)


@dataclass
class ContinuousLoadResult(Result):
    pump_speed: float = rfield("m^3/s", "Required pump speed (actual)")
    pump_speed_normal: float = rfield("m^3/s", "Pump speed at normal conditions")
    y_steam: float = rfield("", "Steam mole fraction")
    y_co2: float = rfield("", "CO2 mole fraction")
    density: float = rfield("kg/m^3", "Mixture density")
    viscosity: float = rfield("Pa·s", "Mixture viscosity")


def continuous_load(P: float, T: float, steam_flow: float, co2_flow: float) -> ContinuousLoadResult:
    """Pump speed for a continuous steam + CO2 load (flows in kg/s) at vessel pressure P [Pa] (ideal gas)."""
    _check_superheated(T, P)
    n_s = steam_flow / fluid("Water").molar_mass
    n_c = co2_flow / fluid("CO2").molar_mass
    n = n_s + n_c
    V = n * R_UNIVERSAL * T / P
    rho, mu = mixture_properties(["Water", "CO2"], [steam_flow, co2_flow], T, P)
    return ContinuousLoadResult(V, V * (P / P_NORMAL) * (T_NORMAL / T), n_s / n, n_c / n, rho, mu)
