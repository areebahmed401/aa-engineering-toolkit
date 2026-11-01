"""
Lumped thermal model of a cell, coupled to the equivalent-circuit model:

    m·cp·dT/dt = Q_gen - Σ hA_i·(T - T_i),     Q_gen = I²R0 + V1²/R1 + V2²/R2 - I·T·dU/dT

(irreversible Joule/polarisation heat plus reversible entropic heat; Bernardi, Pawlikowski & Newman 1985,
J. Electrochem. Soc. 132, 5). Heat transfer coefficients come from :mod:`engtoolkit.thermo.heat_transfer`
with fluid properties from :func:`engtoolkit.materials.fluid`, so the cooling options are driven by the
toolkit's thermodynamics library:

- ``natural_air``: Churchill-Chu natural convection (horizontal cylinder / vertical plate) + radiation
- ``forced_air``: Churchill-Bernstein (cylinder in cross-flow) or laminar/turbulent flat plate
- ``liquid_cold_plate``: water-glycol channel (Gnielinski / laminar Nu) in series with a thermal pad and
  the aluminium plate wall over the cooled area; the rest of the surface sees still air
- ``adiabatic``: no heat removal (worst case)
- ``fixed_h``: a given h over the whole surface to the coolant temperature (e.g. to match another model)

The temperature is advanced with the exact solution for heat generation held constant over a step.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from engtoolkit.catalogs.cells import Cell
from engtoolkit.materials import AIR, fluid, get_material
from engtoolkit.thermo import heat_transfer as ht

CoolingKind = Literal["adiabatic", "natural_air", "forced_air", "liquid_cold_plate", "fixed_h"]
COOLING_LABELS = {
    "adiabatic": "Adiabatic (no cooling)",
    "natural_air": "Natural convection (still air)",
    "forced_air": "Forced air",
    "liquid_cold_plate": "Liquid cold plate",
    "fixed_h": "Fixed heat transfer coefficient",
}
WATER_GLYCOL = "INCOMP::MEG[0.3]"


@dataclass(frozen=True)
class Cooling:
    kind: CoolingKind = "natural_air"
    T_ambient: float = 298.15          # air around the cell [K]
    T_coolant: float = 298.15          # coolant inlet (liquid) or cooling air [K]
    air_velocity: float = 3.0          # forced air [m/s]
    coolant: str = WATER_GLYCOL        # liquid coolant (materials.fluid name)
    coolant_velocity: float = 0.5      # in the cold-plate channel [m/s]
    channel_diameter: float = 0.006    # hydraulic diameter of the channel [m]
    cooled_fraction: float = 0.25      # share of the cell surface on the cold plate
    pad_thickness: float = 1.0e-3      # thermal interface pad [m]
    pad_material: str = "Thermal gap pad"
    plate_thickness: float = 2.0e-3    # aluminium wall between channel and pad [m]
    emissivity: float = 0.8            # cell surface (radiation to the ambient)
    h_fixed: float = 10.0              # for kind "fixed_h" [W/(m²·K)]


@lru_cache(maxsize=4096)
def _h_natural(T_s: float, T_amb: float, L: float, cylinder: bool) -> float:
    if cylinder:
        return ht.natural_convection_horizontal_cylinder(T_s, T_amb, L, AIR)
    return ht.natural_convection_vertical_plate(T_s, T_amb, L, AIR)


def liquid_channel_h(coolant: str, T: float, velocity: float, D_h: float, P: float = 2e5) -> tuple[float, float]:
    """Heat transfer coefficient [W/(m²·K)] and Reynolds number for coolant in a channel."""
    s = fluid(coolant).state(T=T, P=P)
    Re = s.rho * velocity * D_h / s.mu
    return ht.h_from_nusselt(ht.nusselt_internal(Re, s.Pr, boundary="constant_q"), s.k, D_h), Re


@dataclass
class ThermalModel:
    mass: float
    cp: float
    area: float
    L: float                   # characteristic length for convection [m]
    cylinder: bool
    cooling: Cooling = field(default_factory=Cooling)

    def __post_init__(self):
        c = self.cooling
        self.info: dict[str, float] = {}
        self._A_cooled = 0.0
        self._U_cooled = 0.0
        if c.kind == "liquid_cold_plate":
            h_ch, Re = liquid_channel_h(c.coolant, c.T_coolant, c.coolant_velocity, c.channel_diameter)
            k_pad = get_material(c.pad_material).prop("k", c.T_coolant)
            k_al = get_material("Aluminum").prop("k", c.T_coolant)
            # channel wetted area assumed equal to the contact area (one channel under each cooled face)
            self._U_cooled = 1.0 / (1.0 / h_ch + c.pad_thickness / k_pad + c.plate_thickness / k_al)
            self._A_cooled = c.cooled_fraction * self.area
            self.info = {"h_channel": h_ch, "Re_channel": Re, "U_cooled": self._U_cooled}
        elif c.kind == "forced_air":
            T_film = c.T_coolant + 5.0
            if self.cylinder:
                h = ht.forced_convection_cylinder(c.air_velocity, T_film, c.T_coolant, self.L, AIR)
            else:
                h = ht.forced_convection_flat_plate(c.air_velocity, T_film, c.T_coolant, self.L, AIR)
            self._U_cooled, self._A_cooled = h, self.area
            self.info = {"h_forced": h}
        elif c.kind == "fixed_h":
            self._U_cooled, self._A_cooled = c.h_fixed, self.area

    @classmethod
    def for_cell(cls, cell: Cell, cooling: Cooling | None = None) -> ThermalModel:
        return cls(cell.mass, cell.cp, cell.surface_area, cell.characteristic_length,
                   cell.format == "cylindrical", cooling or Cooling())

    @property
    def T_coolant(self) -> float:
        return self.cooling.T_coolant if self.cooling.kind in ("forced_air", "liquid_cold_plate", "fixed_h") \
            else self.cooling.T_ambient

    def sinks(self, T: float) -> list[tuple[float, float]]:
        """(conductance hA [W/K], sink temperature [K]) for each heat path at cell temperature T."""
        c = self.cooling
        if c.kind == "adiabatic":
            return []
        out = []
        if self._A_cooled > 0:
            out.append((self._U_cooled * self._A_cooled, c.T_coolant))
        A_air = self.area - (self._A_cooled if c.kind == "liquid_cold_plate" else 0.0)
        if c.kind in ("natural_air", "liquid_cold_plate") and A_air > 0:
            T_r = int(float(T) * 10 + 0.5) / 10  # 0.1 K steps for the h(T) cache
            h_nat = _h_natural(T_r, c.T_ambient, self.L, self.cylinder)
            h_rad = ht.h_radiation(c.emissivity, T_r, c.T_ambient) if c.emissivity > 0 else 0.0
            out.append(((h_nat + h_rad) * A_air, c.T_ambient))
        return out

    def conductance(self, T: float) -> tuple[float, float]:
        """Total hA [W/K] and the area-averaged h [W/(m²·K)] at cell temperature T."""
        hA = sum(g for g, _ in self.sinks(T))
        return hA, hA / self.area

    def heat_removed(self, T: float) -> float:
        return sum(g * (T - Ts) for g, Ts in self.sinks(T))

    def step(self, T: float, Q_gen: float, dt: float, sinks: list[tuple[float, float]] | None = None) -> float:
        """Temperature after dt with constant heat generation Q_gen (exact for the linearised sinks)."""
        mc = self.mass * self.cp
        if sinks is None:
            sinks = self.sinks(T)
        G = sum(g for g, _ in sinks)
        if G <= 0:
            return T + Q_gen * dt / mc
        T_eq = sum(g * Ts for g, Ts in sinks) / G + Q_gen / G
        return T_eq + (T - T_eq) * math.exp(-G * dt / mc)

    def steady_state(self, Q_gen: float, T_guess: float | None = None) -> float:
        """Cell temperature at which the heat removed equals Q_gen (fixed-point on h(T))."""
        T = T_guess or self.T_coolant + 1.0
        for _ in range(100):
            sinks = self.sinks(T)
            G = sum(g for g, _ in sinks)
            if G <= 0:
                return math.inf
            T_new = sum(g * Ts for g, Ts in sinks) / G + Q_gen / G
            if abs(T_new - T) < 1e-6:
                return T_new
            T = 0.5 * (T + T_new)
        return T
