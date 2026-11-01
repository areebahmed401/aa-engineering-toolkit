"""
ASME: pressure vessel sizing to ASME BPVC Section VIII Division 1.

Layout:
    div1/shells.py             UG-27 cylindrical and spherical shells (internal pressure)
    div1/heads.py              UG-32 ellipsoidal, torispherical, hemispherical; UG-34 flat heads
    div1/nozzles.py            UG-37 reinforcement (area replacement, simplified)
    div1/external_pressure.py  UG-28 (elastic region, factor B supplied by the user)
    div1/common.py             joint efficiencies, UG-16 minimum, standard plates, UG-99(b) hydrotest
    div1/report.py             vessel summary combining shell, heads, nozzles and external pressure
    tools.py, charts.py        registered tools for the notebooks and the web app

Allowable stresses come from ``engtoolkit.materials`` (``allowables.S`` curves entered and verified
by the user against Section II-D) or are entered directly; no code tables are reproduced. Results are
preliminary sizing: verify against the current edition of the code.

Dependency rule: asme may import core, materials, catalogs and structural; never thermo or electrical.
"""
from .div1 import (
    DISCLAIMER, Nozzle, cylindrical_shell, external_pressure_cylinder, flat_head, formed_head, hydrotest_pressure,
    nozzle_reinforcement, spherical_shell, vessel_design,
)
