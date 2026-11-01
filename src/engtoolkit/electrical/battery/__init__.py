"""
Battery models that run anywhere, including the browser (NumPy only):

    from engtoolkit.catalogs import get_cell
    from engtoolkit.electrical.battery import ECMParams, ThermalModel, Cooling, simulate
    cell = get_cell("LG M50 21700 (NMC811)")
    sim = simulate(ECMParams.from_cell(cell), "discharge_cc", c_rate=1.0,
                   thermal=ThermalModel.for_cell(cell, Cooling("natural_air")))

``pybamm_models`` (physics-based SPMe/DFN with degradation) needs the optional ``[battery]`` extra and is
not imported here.
"""
from .aging import MODELS as AGING_MODELS, AgingCurve, cycle_aging
from .ecm import ECMParams, Simulation, simulate
from .thermal import COOLING_LABELS, Cooling, ThermalModel
