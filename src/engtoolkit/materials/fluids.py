"""
Fluids: a thin, consistent wrapper over CoolProp shared by every discipline.

    water = fluid(WATER)                    # IAPWS-IF97 industrial formulation ("IF97::Water"), fast
    water95 = fluid("Water")                # IAPWS-95 reference EOS (CoolProp HEOS library)
    glycol = fluid("INCOMP::MEG[0.3]")      # 30 % mono-ethylene glycol coolant
    air = fluid(AIR)                        # dry air at ~1 atm (Incropera Table A.4), fast
    s = water.state(T=373.15, Q=1)          # any two of T, P, H, S, Q, D, U (SI units)
    s.rho, s.h, s.cp, s.mu, s.k, s.Pr

Speed: plain names like "Water" or "R134a" use CoolProp's HEOS library, which parses every fluid
the first time one is used (~2 s natively, ~1 min in the browser). IF97 water, incompressible
coolants and the built-in air table don't need it. ``needs_fluid_library(name)`` tells which is which.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from engtoolkit.core.results import Result, rfield

from ._coolprop import CP

WATER = "IF97::Water"
AIR = "Air (1 atm table)"

INPUT_KEYS = {"T": "T", "P": "P", "H": "H", "S": "S", "Q": "Q", "D": "D", "U": "U"}
_PARAMS = {"T": CP.iT, "P": CP.iP, "H": CP.iHmass, "S": CP.iSmass, "Q": CP.iQ, "D": CP.iDmass, "U": CP.iUmass}
_OUTPUT_PARAMS = {
    "T": CP.iT, "P": CP.iP, "rho": CP.iDmass, "h": CP.iHmass, "s": CP.iSmass, "u": CP.iUmass,
    "cp": CP.iCpmass, "cv": CP.iCvmass, "mu": CP.iviscosity, "k": CP.iconductivity, "Pr": CP.iPrandtl, "Q": CP.iQ,
}
_PHASES = {
    CP.iphase_liquid: "liquid", CP.iphase_supercritical: "supercritical",
    CP.iphase_supercritical_gas: "supercritical_gas", CP.iphase_supercritical_liquid: "supercritical_liquid",
    CP.iphase_critical_point: "critical_point", CP.iphase_gas: "gas", CP.iphase_twophase: "twophase",
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


def _validated(inputs: dict[str, float]) -> dict[str, float]:
    given = {k: v for k, v in inputs.items() if v is not None}
    unknown = set(given) - set(INPUT_KEYS)
    if unknown:
        raise ValueError(f"Unknown state input(s) {sorted(unknown)}; use two of {list(INPUT_KEYS)}")
    if len(given) != 2:
        raise ValueError(f"Give exactly two state inputs out of {list(INPUT_KEYS)}, got {sorted(given)}")
    return given


def needs_fluid_library(name: str) -> bool:
    """True if the fluid uses CoolProp's HEOS library (slow first load, especially in the browser)."""
    if name == AIR:
        return False
    backend, _, _ = name.rpartition("::")
    return backend.upper() in ("", "HEOS")


class Fluid:
    def __init__(self, name: str):
        self.name = name
        self.is_incompressible = name.upper().startswith("INCOMP::")
        self._fresh_each_time = name.upper().startswith("IF97::")
        self._as = None

    def _abstract_state(self):
        """
        CoolProp AbstractState: one flash per state instead of one PropsSI call per property.
        Reused between calls, except for IF97, whose backend keeps transport properties (viscosity,
        conductivity) cached across updates and would return values from the previous state.
        """
        if self._as is None or self._fresh_each_time:
            backend, _, body = self.name.rpartition("::")
            if backend.upper() == "INCOMP":
                match = re.fullmatch(r"([^\[]+)(?:\[([0-9.eE+-]+)\])?", body)
                state = CP.AbstractState("INCOMP", match.group(1))
                if match.group(2):
                    state.set_mass_fractions([float(match.group(2))])
            else:
                state = CP.AbstractState(backend or "HEOS", body)
            self._as = state
        return self._as

    def _update(self, inputs: dict[str, float]):
        given = _validated(inputs)
        (k1, v1), (k2, v2) = given.items()
        st = self._abstract_state()
        st.update(*CP.generate_update_pair(_PARAMS[k1], v1, _PARAMS[k2], v2))
        return st

    def prop(self, output: str, **inputs) -> float:
        """One output (toolkit name like 'rho', 'cp', or a CoolProp key like 'Dmass') for a state."""
        param = _OUTPUT_PARAMS.get(output)
        if param is None:
            param = CP.get_parameter_index(output)
        return self._update(inputs).keyed_output(param)

    def state(self, **inputs) -> FluidState:
        """Full state from any two of T, P, H, S, Q, D, U (SI). Undefined properties come back NaN."""
        st = self._update(inputs)

        def get(fn):
            try:
                return fn()
            except ValueError:
                return math.nan

        Q = get(st.Q)
        phase = "liquid" if self.is_incompressible else _PHASES.get(get(st.phase), "")
        return FluidState(
            fluid=self.name, phase=phase, T=st.T(), P=st.p(), rho=st.rhomass(), h=st.hmass(), s=st.smass(),
            u=get(st.umass), cp=get(st.cpmass), cv=get(st.cvmass), mu=get(st.viscosity), k=get(st.conductivity),
            Pr=get(st.Prandtl), Q=Q if 0.0 <= Q <= 1.0 else math.nan,
        )

    def saturation(self, T: float | None = None, P: float | None = None) -> tuple[FluidState, FluidState]:
        """Saturated liquid and vapour states at T or P."""
        if (T is None) == (P is None):
            raise ValueError("Give either T or P")
        given = {"T": T} if T is not None else {"P": P}
        return self.state(**given, Q=0), self.state(**given, Q=1)

    # ----- constants (from the fluid's own backend, so IF97 never loads HEOS) -----
    def _const(self, method: str, key: str) -> float:
        try:
            return getattr(self._abstract_state(), method)()
        except (ValueError, AttributeError):
            return CP.PropsSI(key, self.name)

    @property
    def T_critical(self) -> float:
        return self._const("T_critical", "Tcrit")

    @property
    def P_critical(self) -> float:
        return self._const("p_critical", "pcrit")

    @property
    def T_triple(self) -> float:
        return self._const("Ttriple", "Ttriple")

    @property
    def T_min(self) -> float:
        return self._const("Tmin", "Tmin")

    @property
    def molar_mass(self) -> float:
        """kg/mol"""
        return self._const("molar_mass", "M")

    def __repr__(self) -> str:
        return f"Fluid({self.name!r})"


class TabulatedAir:
    """
    Dry air near atmospheric pressure from Incropera Table A.4 (1 atm), ideal-gas density at P.
    Only T and P inputs; used for convection to ambient air (fast, no fluid library needed).
    """
    name = AIR
    is_incompressible = False
    R = 287.05  # J/(kg·K)
    molar_mass = 0.028965
    # T [K], mu [Pa·s], k [W/(m·K)], cp [J/(kg·K)]
    _T = np.array([100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800], dtype=float)
    _mu = np.array([71.1, 103.4, 132.5, 159.6, 184.6, 208.2, 230.1, 250.7, 270.1, 288.4, 305.8, 322.5,
                    338.8, 354.6, 369.8]) * 1e-7
    _k = np.array([9.34, 13.8, 18.1, 22.3, 26.3, 30.0, 33.8, 37.3, 40.7, 43.9, 46.9, 49.7, 52.4, 54.9, 57.3]) * 1e-3
    _cp = np.array([1032, 1012, 1007, 1006, 1007, 1009, 1014, 1021, 1030, 1040, 1051, 1063, 1075, 1087, 1099],
                   dtype=float)

    def state(self, T: float | None = None, P: float = 101325.0, **other) -> FluidState:
        if T is None or other:
            raise ValueError("Tabulated air takes T and P only")
        if not self._T[0] <= T <= self._T[-1]:
            raise ValueError(f"Tabulated air covers {self._T[0]:.0f}-{self._T[-1]:.0f} K, got {T:.1f} K")
        mu, k, cp = (float(np.interp(T, self._T, arr)) for arr in (self._mu, self._k, self._cp))
        rho = P / (self.R * T)
        return FluidState(fluid=self.name, phase="gas", T=T, P=P, rho=rho, cp=cp, cv=cp - self.R, mu=mu, k=k,
                          Pr=mu * cp / k, h=cp * (T - 273.15), u=(cp - self.R) * (T - 273.15))

    def prop(self, output: str, **inputs) -> float:
        return getattr(self.state(**inputs), output)

    def __repr__(self) -> str:
        return "TabulatedAir()"


@lru_cache(maxsize=64)
def fluid(name: str) -> Fluid | TabulatedAir:
    """Shared Fluid object for a CoolProp fluid string (or ``AIR`` for the built-in air table)."""
    if name == AIR:
        return TabulatedAir()
    return Fluid(name)


def list_fluids() -> list[str]:
    """Pure and pseudo-pure CoolProp fluids (incompressibles use the 'INCOMP::' prefix). Loads HEOS."""
    return sorted(CP.get_global_param_string("fluids_list").split(","))


def list_incompressibles() -> list[str]:
    """Incompressible coolants, e.g. 'MEG' (use as 'INCOMP::MEG[0.3]' with a mass fraction)."""
    return sorted(CP.get_global_param_string("incompressible_list_solution").split(","))
