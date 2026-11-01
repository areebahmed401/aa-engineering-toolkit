"""
AA Engineering Toolkit.

Sub-packages (import only what you need):
    engtoolkit.core        units, results, tool registry
    engtoolkit.materials   shared solid and fluid properties
    engtoolkit.catalogs    standard sizes (pipes, profiles, fittings)
    engtoolkit.thermo      thermodynamics, fluids and heat transfer
    engtoolkit.structural  sections, beams, FEM, torsion
    engtoolkit.electrical  battery modelling
    engtoolkit.asme        ASME pressure vessel sizing

Run any registered tool:  ``engtoolkit.run("thermo.pipe_pressure_drop", length=100)``
"""
__version__ = "0.2.0"

from engtoolkit.core.registry import get_tool, list_tools, run  # noqa: E402

__all__ = ["__version__", "run", "get_tool", "list_tools"]
