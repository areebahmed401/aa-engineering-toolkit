"""
ASME: pressure vessel sizing to ASME BPVC Section VIII Division 1 (Phase 4 of the roadmap).

Planned layout:
    div1/shells.py             UG-27 cylindrical and spherical shells (internal pressure)
    div1/heads.py              UG-32 ellipsoidal, torispherical, hemispherical; UG-34 flat heads
    div1/nozzles.py            UG-37 reinforcement (area replacement, simplified)
    div1/external_pressure.py  UG-28 (elastic region, factor B supplied by the user)
    div1/report.py             summary report

Allowable stresses come from ``engtoolkit.materials`` (``allowables.S`` curves entered and verified
by the user against Section II-D); no code tables are reproduced.

Dependency rule: asme may import core, materials, catalogs and structural; never thermo or electrical.
"""
