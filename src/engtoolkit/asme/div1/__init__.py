"""
ASME BPVC Section VIII Division 1 pressure vessel sizing (internal pressure, external pressure on
cylinders, nozzle reinforcement and hydrostatic test).

    from engtoolkit.asme.div1 import cylindrical_shell, formed_head, vessel_design
    shell = cylindrical_shell(P=1.0e6, D_inside=1.2, S=138e6, E=0.85, corrosion=3e-3)
    shell.t_required, shell.mawp

Preliminary sizing only: verify every result against the current edition of the code. Allowable
stresses (Section II-D) and the UG-28 chart factors are user inputs; no code tables are reproduced.
"""
from .common import (
    DISCLAIMER, JOINT_EFFICIENCIES, STANDARD_PLATES, UG16_MIN_THICKNESS, HydrotestResult, hydrotest_pressure,
    next_plate,
)
from .external_pressure import ExternalPressureResult, external_pressure_cylinder, factor_A
from .heads import FLAT_HEAD_C, HeadResult, ellipsoid_K, flat_head, formed_head, head_depth, torisphere_M
from .nozzles import NozzleResult, nozzle_reinforcement, required_host_thickness
from .report import Nozzle, VesselDesignResult, vessel_design
from .shells import ShellResult, cylindrical_shell, spherical_shell
