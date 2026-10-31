"""
Fluids: a thin, consistent wrapper over CoolProp shared by every discipline.

    water = fluid("Water")                  # IAPWS-95 (CoolProp default)
    steam = fluid("IF97::Water")            # IAPWS-IF97 industrial formulation
    glycol = fluid("INCOMP::MEG[0.3]")      # 30 % mono-ethylene glycol coolant
    s = water.state(T=373.15, Q=1)          # any two of T, P, H, S, Q, D, U (SI units)
    s.rho, s.h, s.cp, s.mu, s.k, s.Pr
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import CoolProp.CoolProp as CP

from engtoolkit.core.results import Result, rfield

INPUT_KEYS = {"T": "T", "P": "P", "H": "H", "S": "S", "Q": "Q", "D": "D", "U": "U"}

_OUTPUTS = {
    "T": "T", "P": "P", "rho": "D", "h": "H", "s": "S", "u": "U",
    "cp": "C", "cv": "O", "mu": "V", "k": "L", "Pr": "Prandtl", "Q": "Q",
}


@dataclass
class FluidState(Result):
    fluid: str = rfield("", "Fluid", default="")
    phase: str = rfield("", "Phase", default="")
    T: float = rfield("K", "Temperature", default=math.nan)
    P: float = rfield("Pa", "Pressure", default=math.nan)
    rho: float = rfield("kg/m^3", "Density", default=math.nan)
    h: float = rfield("J/kg", "Specific enthalpy", default=math.nan)
    s: float = rfield("J/(kg·K)", "Specific entropy", default=math.nan)
    u: float = rfield("J/kg", "Specific internal energy", default=math.nan)
    cp: float = rfield("J/(kg·K)", "Specific heat cp", default=math.nan)
    cv: float = rfield("J/(kg·K)", "Specific heat cv", default=math.nan)
    mu: float = rfield("Pa·s", "Dynamic viscosity", default=math.nan)
    k: float = rfield("W/(m·K)", "Thermal conductivity", default=math.nan)
    Pr: float = rfield("", "Prandtl number", default=math.nan)
    Q: float = rfield("", "Vapour quality", default=math.nan)

    @property
    def v(self) -> float:
        """Specific volume [m³/kg]."""
        return 1.0 / self.rho

    @property
    def nu(self) -> float:
        """Kinematic viscosity [m²/s]."""
        return self.mu / self.rho


class Fluid:
    def __init__(self, name: str):
        self.name = name
        self.is_incompressible = name.upper().startswith("INCOMP::")

    def _pair(self, inputs: dict[str, float]) -> tuple[str, float, str, float]:
        given = {k: v for k, v in inputs.items() if v is not None}
        unknown = set(given) - set(INPUT_KEYS)
        if unknown:
            raise ValueError(f"Unknown state input(s) {sorted(unknown)}; use two of {list(INPUT_KEYS)}")
        if len(given) != 2:
            raise ValueError(f"Give exactly two state inputs out of {list(INPUT_KEYS)}, got {sorted(given)}")
        (k1, v1), (k2, v2) = given.items()
        return INPUT_KEYS[k1], v1, INPUT_KEYS[k2], v2

    def prop(self, output: str, **inputs) -> float:
        """One CoolProp output (CoolProp key or toolkit name like 'rho', 'cp') for a state."""
        key = _OUTPUTS.get(output, output)
        n1, v1, n2, v2 = self._pair(inputs)
        return CP.PropsSI(key, n1, v1, n2, v2, self.name)

    def state(self, **inputs) -> FluidState:
        """Full state from any two of T, P, H, S, Q, D, U (SI). Undefined properties come back NaN."""
        n1, v1, n2, v2 = self._pair(inputs)
        values = {}
        for name, key in _OUTPUTS.items():
            try:
                values[name] = CP.PropsSI(key, n1, v1, n2, v2, self.name)
            except ValueError:
                values[name] = math.nan
        if not (0.0 <= values.get("Q", math.nan) <= 1.0):
            values["Q"] = math.nan
        if self.is_incompressible:
            phase = "liquid"
        else:
            try:
                phase = CP.PhaseSI(n1, v1, n2, v2, self.name)
            except ValueError:
                phase = ""
            if phase.startswith("unknown"):
                phase = ""
        return FluidState(fluid=self.name, phase=phase, **values)

    def saturation(self, T: float | None = None, P: float | None = None) -> tuple[FluidState, FluidState]:
        """Saturated liquid and vapour states at T or P."""
        if (T is None) == (P is None):
            raise ValueError("Give either T or P")
        given = {"T": T} if T is not None else {"P": P}
        return self.state(**given, Q=0), self.state(**given, Q=1)

    # ----- constants -----
    def _const(self, key: str) -> float:
        return CP.PropsSI(key, self.name)

    @property
    def T_critical(self) -> float:
        return self._const("Tcrit")

    @property
    def P_critical(self) -> float:
        return self._const("pcrit")

    @property
    def T_triple(self) -> float:
        return self._const("Ttriple")

    @property
    def T_min(self) -> float:
        return self._const("Tmin")

    @property
    def molar_mass(self) -> float:
        """kg/mol"""
        return self._const("M")

    def __repr__(self) -> str:
        return f"Fluid({self.name!r})"


@lru_cache(maxsize=64)
def fluid(name: str) -> Fluid:
    """Shared Fluid object for a CoolProp fluid string."""
    return Fluid(name)


def list_fluids() -> list[str]:
    """Pure and pseudo-pure CoolProp fluids (incompressibles use the 'INCOMP::' prefix)."""
    return sorted(CP.get_global_param_string("fluids_list").split(","))


def list_incompressibles() -> list[str]:
    """Incompressible coolants, e.g. 'MEG' (use as 'INCOMP::MEG[0.3]' with a mass fraction)."""
    return sorted(CP.get_global_param_string("incompressible_list_solution").split(","))
