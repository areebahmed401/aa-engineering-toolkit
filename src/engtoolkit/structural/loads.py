"""
Loads, supports and the static determinacy check for single-span beams.

Sign convention (SI units):
- P and w are positive DOWNWARD [N], [N/m]
- M is positive COUNTER-CLOCKWISE [N·m]
- Deflection v is positive upward, sagging bending moment is positive
"""
from __future__ import annotations


# --------------------- LOAD DEFINITIONS ---------------------
class Load:
    pass


class PointLoad(Load):
    def __init__(self, P, x):
        self.P = P
        self.x = x


class DistributedLoad(Load):
    def __init__(self, w, x1=0.0, x2=None):
        self.w = w
        self.x1 = x1
        self.x2 = x2


class MomentLoad(Load):
    def __init__(self, M, x):
        self.M = M
        self.x = x


# ------------------- END CONDITIONS -----------------------
# Beam nodes have two DOFs: 0 = transverse deflection v, 1 = rotation theta.
# Axial DOFs are not modelled.
class EndCondition:
    name = "free"
    transverse_reactions = 0  # vertical force / moment reactions it provides

    def constrained_dofs(self):
        return []


class Fixed(EndCondition):
    name = "fixed"
    transverse_reactions = 2  # V + M

    def constrained_dofs(self):
        return [0, 1]  # v and theta


class Pinned(EndCondition):
    name = "pinned"
    transverse_reactions = 1  # V (its horizontal reaction does not resist transverse load)

    def constrained_dofs(self):
        return [0]  # v only, free to rotate


class Roller(EndCondition):
    name = "roller"
    transverse_reactions = 1  # V only

    def constrained_dofs(self):
        return [0]  # v only (axial movement free)


class Free(EndCondition):
    name = "free"

    def constrained_dofs(self):
        return []


SUPPORTS = {"fixed": Fixed, "pinned": Pinned, "roller": Roller, "free": Free}


def support(name: str) -> EndCondition:
    try:
        return SUPPORTS[name.lower()]()
    except KeyError:
        raise ValueError(f"Unknown support {name!r}; use one of {list(SUPPORTS)}") from None


# ------------------- HELPER FUNCTIONS --------------------
def add_point_load(beam, P, x):
    beam.loads.append(PointLoad(P, x))
    return beam


def add_distributed_load(beam, w, x1=0.0, x2=None):
    beam.loads.append(DistributedLoad(w, x1, x2))
    return beam


def add_moment_load(beam, M, x):
    beam.loads.append(MomentLoad(M, x))
    return beam


def set_end_conditions(beam, left=None, right=None):
    if left is not None:
        beam.left_end = left
    if right is not None:
        beam.right_end = right
    return beam


# ------------------- STATIC DETERMINACY CHECK ----------------
def static_determinacy(beam) -> int:
    """
    Degree of static indeterminacy of a single-span beam under transverse load.
    Reactions counted: fixed 2 (V, M), pinned 1, roller 1, free 0; equations: ΣFy, ΣM.
      < 0  mechanism (not enough supports)
      = 0  statically determinate: equilibrium is enough
      > 0  statically indeterminate: compatibility needed (FEM, force method)
    """
    if beam.left_end is None or beam.right_end is None:
        raise ValueError("Beam end conditions not set")
    return beam.left_end.transverse_reactions + beam.right_end.transverse_reactions - 2
