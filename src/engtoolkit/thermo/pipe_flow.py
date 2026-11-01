"""
Single-phase pipe flow: friction (Darcy-Weisbach + Colebrook) and fittings (Crane TP-410).
SI units throughout (m, Pa, K, m³/s).
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from engtoolkit.catalogs import crane_le_over_d, pipes
from engtoolkit.core.results import Result, rfield
from engtoolkit.materials import Material, fluid, get_material

from .friction import G, colebrook_white, fully_turbulent_friction_factor


class Pipe:
    def __init__(self, diameter: float, length: float, material: str | Material = "Carbon Steel",
                 roughness: float | None = None):
        self.D = diameter   # inner diameter [m]
        self.L = length     # [m]
        self.material = get_material(material)
        self.roughness = roughness if roughness is not None else self.material.roughness
        if self.roughness is None:
            raise ValueError(f"Material {self.material.name!r} has no roughness; pass roughness=")

    @classmethod
    def from_catalog(cls, dn: int, schedule: str = "40", length: float = 1.0,
                     material: str | Material = "Carbon Steel") -> "Pipe":
        return cls(pipes.pipe(dn, schedule).id, length, material)

    @property
    def area(self) -> float:
        return math.pi * self.D**2 / 4


class PipeFlow:
    def __init__(self, pipe: Pipe, fluid_name: str, T: float, P: float):
        """fluid_name: CoolProp fluid string; T [K]; P [Pa]."""
        self.pipe = pipe
        self.fluid = fluid_name
        self.T = T
        self.P = P
        self._state = fluid(fluid_name).state(T=T, P=P)

    @property
    def density(self) -> float:
        return self._state.rho

    @property
    def viscosity(self) -> float:
        return self._state.mu

    def velocity(self, Q: float) -> float:
        return Q / self.pipe.area

    def reynolds(self, Q: float) -> float:
        return self.density * self.velocity(Q) * self.pipe.D / self.viscosity

    def friction_factor(self, Q: float) -> float:
        return colebrook_white(self.reynolds(Q), self.pipe.roughness, self.pipe.D)

    def fully_turbulent_friction_factor(self) -> float:
        return fully_turbulent_friction_factor(self.pipe.roughness, self.pipe.D)

    def pressure_drop(self, Q: float) -> float:
        """Frictional pressure drop over the pipe length [Pa]."""
        v = self.velocity(Q)
        return self.friction_factor(Q) * (self.pipe.L / self.pipe.D) * 0.5 * self.density * v**2


#------------ FLOW ELEMENTS: Pipe & Fittings/Valves ------------

class FlowElement(ABC):
    @abstractmethod
    def pressure_drop(self, Q: float) -> float:
        pass


class PipeElement(FlowElement):  # pressure loss due to pipe friction
    def __init__(self, pipe_flow: PipeFlow):
        self.flow = pipe_flow

    def pressure_drop(self, Q):
        return self.flow.pressure_drop(Q)


class CraneMinorLoss(FlowElement):  # pressure loss due to fittings via Crane TP-410
    def __init__(self, fitting_type: str, pipe_flow: PipeFlow, le_over_d: dict | None = None, count: int = 1):
        self.pipe_flow = pipe_flow
        self.count = count
        data = le_over_d if le_over_d is not None else crane_le_over_d()
        try:
            self.Le_over_D = data[fitting_type]
        except KeyError:
            raise ValueError(f"Unknown Crane fitting: {fitting_type}. Known: {sorted(data)}") from None

    @property
    def K(self) -> float:
        # Crane TP-410: K = f_T * (L/D), f_T = fully turbulent friction factor of the pipe
        return self.pipe_flow.fully_turbulent_friction_factor() * self.Le_over_D

    def pressure_drop(self, Q):
        v = self.pipe_flow.velocity(Q)
        return self.count * self.K * 0.5 * self.pipe_flow.density * v**2


class PipeLine:  # complete pipe line
    def __init__(self):
        self.elements: list[FlowElement] = []

    def add(self, element: FlowElement) -> None:
        self.elements.append(element)

    def total_pressure_drop(self, Q: float) -> float:
        return sum(e.pressure_drop(Q) for e in self.elements)


# ---------------- functional API used by notebooks and the web app ----------------

FITTING_FIELDS = {
    "elbow_90_standard": "n_elbow_90",
    "elbow_90_LR": "n_elbow_90_LR",
    "elbow_45": "n_elbow_45",
    "tee_straight": "n_tee_straight",
    "tee_branch": "n_tee_branch",
    "gate_valve_open": "n_gate_valve",
    "ball_valve_open": "n_ball_valve",
    "globe_valve_open": "n_globe_valve",
    "check_valve_swing": "n_check_valve",
}


@dataclass
class PipeDropResult(Result):
    dp_total: float = rfield("Pa", "Total pressure drop")
    dp_friction: float = rfield("Pa", "Friction pressure drop")
    dp_fittings: float = rfield("Pa", "Fittings pressure drop")
    dp_elevation: float = rfield("Pa", "Elevation pressure change")
    velocity: float = rfield("m/s", "Velocity")
    reynolds: float = rfield("", "Reynolds number")
    friction_factor: float = rfield("", "Darcy friction factor")
    regime: str = rfield("", "Flow regime")
    density: float = rfield("kg/m^3", "Density")
    inner_diameter: float = rfield("m", "Inner diameter")
    volumetric_flow: float = rfield("m^3/s", "Volumetric flow")
    head_loss: float = rfield("m", "Friction + fittings head loss")
    fluid_state: str = rfield("", "Fluid state", default="")
    fittings: dict = rfield("", "Fittings (count)", default_factory=dict, summary=False)


def pipe_pressure_drop(
    fluid_name: str, T: float, P: float, inner_diameter: float, length: float,
    mass_flow: float | None = None, volumetric_flow: float | None = None,
    material: str | Material = "Carbon Steel", fittings: dict[str, int] | None = None,
    elevation_change: float = 0.0,
) -> PipeDropResult:
    """
    Pressure drop along a pipe [Pa]: friction + Crane fittings + elevation (outlet minus inlet height).
    Give either mass_flow [kg/s] or volumetric_flow [m³/s].
    """
    if (mass_flow is None) == (volumetric_flow is None):
        raise ValueError("Give either mass_flow or volumetric_flow")
    flow = PipeFlow(Pipe(inner_diameter, length, material), fluid_name, T, P)
    Q = volumetric_flow if volumetric_flow is not None else mass_flow / flow.density
    fittings = {k: int(v) for k, v in (fittings or {}).items() if v}
    dp_fit = sum(CraneMinorLoss(name, flow, count=n).pressure_drop(Q) for name, n in fittings.items())
    dp_fric = flow.pressure_drop(Q)
    dp_elev = flow.density * G * elevation_change
    Re = flow.reynolds(Q)
    regime = "laminar" if Re <= 2300 else ("transitional" if Re < 4000 else "turbulent")
    return PipeDropResult(
        dp_total=dp_fric + dp_fit + dp_elev, dp_friction=dp_fric, dp_fittings=dp_fit, dp_elevation=dp_elev,
        velocity=flow.velocity(Q), reynolds=Re, friction_factor=flow.friction_factor(Q), regime=regime,
        density=flow.density, inner_diameter=inner_diameter, volumetric_flow=Q,
        head_loss=(dp_fric + dp_fit) / (flow.density * G), fittings=fittings,
        fluid_state=flow._state.state,
    )


@dataclass
class SizeSweepRow(Result):
    dn: int = rfield("", "DN")
    inner_diameter: float = rfield("m", "Inner diameter")
    velocity: float = rfield("m/s", "Velocity")
    dp_total: float = rfield("Pa", "Pressure drop")
    cost: float = rfield("USD", "Pipe cost")
    acceptable: bool = rfield("", "Within limits")


def pipe_size_sweep(fluid_name: str, T: float, P: float, length: float, mass_flow: float,
                    schedule: str = "40", dn_range: tuple[int, int] = (15, 300),
                    material: str | Material = "Carbon Steel", fittings: dict[str, int] | None = None,
                    v_max: float | None = None, dp_max: float | None = None) -> list[SizeSweepRow]:
    """Velocity, pressure drop and cost for each catalog size in a DN range."""
    rows = []
    for size in pipes.sizes(schedule):
        if not dn_range[0] <= size.dn <= dn_range[1]:
            continue
        r = pipe_pressure_drop(fluid_name, T, P, size.id, length, mass_flow=mass_flow,
                               material=material, fittings=fittings)
        try:
            cost = pipes.cost_per_m(size.dn) * length
        except KeyError:
            cost = math.nan
        ok = (v_max is None or r.velocity <= v_max) and (dp_max is None or r.dp_total <= dp_max)
        rows.append(SizeSweepRow(size.dn, size.id, r.velocity, r.dp_total, cost, ok))
    return rows


class PipeSizer:
    """Kept for the notebooks: sizing helpers around a fixed fluid state and length."""

    def __init__(self, fluid_name: str, material: str | Material, T: float, P: float, length: float):
        self.fluid_name = fluid_name
        self.material = get_material(material)
        self.T = T
        self.P = P
        self.length = length

    def size_for_max_velocity(self, Q: float, v_max: float) -> float:
        """Inner diameter [m] giving exactly v_max."""
        return (4 * Q / (math.pi * v_max)) ** 0.5

    def size_for_max_dp(self, Q: float, dp_max: float, diameters) -> float:
        """Smallest diameter from ``diameters`` whose friction drop is within dp_max."""
        for D in sorted(diameters):
            flow = PipeFlow(Pipe(D, self.length, self.material), self.fluid_name, self.T, self.P)
            if flow.pressure_drop(Q) <= dp_max:
                return D
        raise ValueError("No diameter satisfies pressure drop constraint")

    def sweep(self, mass_flow: float, schedule: str = "40", dn_range=(15, 300), fittings=None):
        return pipe_size_sweep(self.fluid_name, self.T, self.P, self.length, mass_flow, schedule, dn_range,
                               self.material, fittings)
