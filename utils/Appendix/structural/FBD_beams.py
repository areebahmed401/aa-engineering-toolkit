"""
FBD_beams.py
============
Defines:
- Loads and end conditions
- Helper functions to attach loads/supports to beams
- Free Body Diagram plotting
- Simple static determinacy check
"""

import numpy as np
import matplotlib.pyplot as plt

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

# ------------------- END CONDITIONS  (x, y theta)-----------------------
class EndCondition:
    def constrained_dofs(self):
        return []

class Fixed(EndCondition):
    def constrained_dofs(self):
        return [0, 1, 2]  # x, y, theta

class Pinned(EndCondition):
    def constrained_dofs(self):
        return [0, 2]  # x, theta (y is free)

class Roller(EndCondition):
    def constrained_dofs(self):
        return [1]  # y only (x and theta are free)

class Free(EndCondition):
    def constrained_dofs(self):
        return []

# ------------------- HELPER FUNCTIONS --------------------
def add_point_load(beam, P, x):
    if not hasattr(beam, "loads"):
        beam.loads = []
    beam.loads.append(PointLoad(P, x))
    return beam

def add_distributed_load(beam, w, x1=0.0, x2=None):
    if not hasattr(beam, "loads"):
        beam.loads = []
    beam.loads.append(DistributedLoad(w, x1, x2))
    return beam

def add_moment_load(beam, M, x):
    if not hasattr(beam, "loads"):
        beam.loads = []
    beam.loads.append(MomentLoad(M, x))
    return beam

def set_end_conditions(beam, left=None, right=None):
    if left is not None:
        beam.left_end = left
    if right is not None:
        beam.right_end = right
    return beam

# ------------------- STATIC DETERMINACY CHECK ----------------
def static_determinacy(beam):
    """
    Degree of static indeterminacy for a single-span 2D beam
    (vertical loading only, no axial effects)
    """

    if not hasattr(beam, "left_end") or not hasattr(beam, "right_end"):
        raise ValueError("Beam end conditions not set")

    def reactions(end):
        from FBD_beams import Fixed, Pinned, Roller
        if isinstance(end, Fixed):
            return 3    # V + M
        if isinstance(end, Pinned):
            return 2    # V only
        if isinstance(end, Roller):
            return 1    # V only
        return 0

    r = reactions(beam.left_end) + reactions(beam.right_end)

    eq = 3  # ΣFy = 0, ΣM = 0

    return r - eq

# ------------------- FBD PLOTTING --------------------------
def plot_fbd(beam, scale_force=None, scale_moment=None, scale_udl=None):
    """
    Plots only the Free Body Diagram of a beam:
    - Loads (point, distributed, moment)
    - Supports
    """
    import matplotlib.pyplot as plt

    L = beam.length
    fig, ax = plt.subplots(figsize=(24,4))

    # Adaptive scaling
    max_F = max([abs(load.P) for load in getattr(beam, "loads", []) if isinstance(load, PointLoad)] + [1.0])
    max_M = max([abs(load.M) for load in getattr(beam, "loads", []) if isinstance(load, MomentLoad)] + [1.0])
    max_w = max([abs(load.w) for load in getattr(beam, "loads", []) if isinstance(load, DistributedLoad)] + [1.0])

    force_scale = scale_force or 0.3*L/max_F
    moment_scale = scale_moment or 0.2*L/max_M
    udl_scale = scale_udl or 0.15*L/max_w

    # Beam line
    ax.plot([0, L], [0, 0], linewidth=4, color='black')

    # Loads
    if hasattr(beam, "loads"):
        for load in beam.loads:
            if isinstance(load, PointLoad):
                h = load.P*force_scale
                ax.arrow(load.x, 0, 0, -h, head_width=0.02*L, head_length=0.05*L,
                         length_includes_head=True, color='blue')
                ax.text(load.x, -1.15*h, f"{load.P:.1f} N", ha='center', va='bottom',
                        color='blue', fontsize=8, fontweight='bold')
            elif isinstance(load, DistributedLoad):
                x2 = load.x2 if load.x2 is not None else L
                xs = np.linspace(load.x1, x2, max(int((x2-load.x1)/0.1), 2))
                for x in xs:
                    h = load.w*udl_scale
                    ax.arrow(x, 0, 0, -h, head_width=0.01*L, head_length=0.03*L,
                             length_includes_head=True, color='green')
                F_eq = load.w*(x2-load.x1)
                ax.text((load.x1+x2)/2, -0.3*L, f"{F_eq:.1f} N", ha='center', va='bottom',
                        color='green', fontsize=8, fontweight='bold')
            elif isinstance(load, MomentLoad):
                r = abs(load.M)*moment_scale
                theta = np.linspace(0, np.pi, 50)
                ax.plot(load.x + r*np.cos(theta), r*np.sin(theta), color='red')
                ax.text(load.x, r*1.3, f"{load.M:.1f} Nm", ha='center', va='bottom',
                        color='red', fontsize=8, fontweight='bold')

    # Supports
    for end, xpos in [(getattr(beam, "left_end", None), 0),
                      (getattr(beam, "right_end", None), L)]:
        if end is None:
            continue
        if isinstance(end, Fixed):
            ax.add_patch(plt.Rectangle((xpos-0.05*L, -0.1*L), 0.1*L, 0.2*L, color='black'))
        elif isinstance(end, Pinned):
            ax.plot(xpos, -0.05*L, marker='^', markersize=12)
        elif isinstance(end, Roller):
            ax.plot(xpos, -0.05*L, marker='o', markersize=8)

    ax.set_aspect('equal')
    ax.set_xlim(-0.05*L, 1.05*L)
    ax.set_ylim(-0.5*L, 0.5*L)
    ax.axis('off')
    plt.show()



