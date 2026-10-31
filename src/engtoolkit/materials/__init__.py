"""
Shared material properties for every discipline.

Solids (metals, polymers, composites, insulation) are loaded from the YAML files in ``data/``;
fluids wrap CoolProp.

    from engtoolkit.materials import get_material, fluid
    steel = get_material("ASTM A106B")
    steel.prop("k", T=473.15)            # temperature-dependent conductivity [W/m·K]
    fluid("Water").state(T=373.15, Q=1)  # saturated steam
"""
from .fluids import (
    AIR, WATER, Fluid, FluidState, TabulatedAir, fluid, list_fluids, list_incompressibles, needs_fluid_library,
)
from .library import add_material, families, get_material, list_materials, load_materials
from .model import PROPERTY_GROUPS, Material, TemperatureCurve
