"""
Electrical: battery modelling (Phase 5 of the roadmap).

Planned layout (see ``engtoolkit/_template`` for the structure every discipline follows):
    battery/ecm.py            1RC/2RC equivalent-circuit model (browser-ready, NumPy/SciPy)
    battery/thermal.py        lumped thermal model; coolant h from engtoolkit.thermo.heat_transfer
                              with engtoolkit.materials.fluid properties
    battery/aging.py          semi-empirical calendar + cycle aging vs C-rate and temperature
    battery/pybamm_models.py  PyBaMM SPMe/DFN with thermal + degradation (optional extra
                              ``[battery]``, imported lazily; not available in the browser)

Dependency rule: electrical may import core, materials, catalogs and thermo; never structural or asme.
"""
