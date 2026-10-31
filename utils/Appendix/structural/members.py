"""
Cross-sections and structural members.

Units: SI throughout (m, m², m⁴, kg/m³).

Axis convention for every cross-section:
- y-axis : horizontal, bending about y is the "strong axis" bending (Iyy)
- z-axis : vertical
- Positions (CoG_*, CoS_*) are measured from the bottom-left corner of the
  section's bounding box: *_y is the vertical position, *_z the horizontal one.
"""

from abc import ABC, abstractmethod
import math

# =========================================================
# 1. CROSS-SECTION BASE CLASS
# =========================================================

class cross_section(ABC):

    @property
    @abstractmethod
    def area(self) -> float:
        pass

    @property
    @abstractmethod
    def Iyy(self) -> float:
        pass

    @property
    @abstractmethod
    def Izz(self) -> float:
        pass

    # Aliases kept so existing notebooks (shape.Iy / shape.Iz) keep working
    @property
    def Iy(self) -> float:
        return self.Iyy

    @property
    def Iz(self) -> float:
        return self.Izz

    @property
    def Iyz(self) -> float:  # Product of inertia, zero for sections with a symmetry axis
        return 0.0

    @property
    def Ip(self) -> float:  # Polar moment of area about the centroid
        return self.Iyy + self.Izz

    @property
    def Rg(self) -> float:  # Radius of gyration about the y-axis
        return (self.Iyy / self.area) ** 0.5

    # Old spelling aliases for torsion properties
    @property
    def J_Torsion(self) -> float:
        return self.J_torsion

    @property
    def W_Torsion(self) -> float:
        return self.W_torsion

    # Shear centre defaults to the centroid (doubly symmetric sections)
    @property
    def CoS_y(self) -> float:
        return self.CoG_y

    @property
    def CoS_z(self) -> float:
        return self.CoG_z


# =========================================================
# 2. CROSS-SECTION IMPLEMENTATIONS (RECTANGLE, CIRCLE, I-BEAM, ETC.)
# =========================================================

#---------- SOLID AND CLOSED PROFILES -------------------

class Rectangle(cross_section):
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height

    @property
    def area(self):
        return self.width * self.height

    @property
    def Iyy(self):
        return self.width * self.height**3 / 12

    @property
    def Izz(self):
        return self.height * self.width**3 / 12

    @property
    def CoG_y(self):
        return self.height / 2

    @property
    def CoG_z(self):
        return self.width / 2

    @property
    def J_torsion(self):
        # Saint-Venant torsion constant, a = long side, b = short side (Roark)
        a, b = max(self.width, self.height), min(self.width, self.height)
        return a * b**3 * (1/3 - 0.21 * (b/a) * (1 - b**4 / (12 * a**4)))

    @property
    def W_torsion(self):
        # Torsional section modulus, tau_max = T / W_t (Roark)
        a, b = max(self.width, self.height), min(self.width, self.height)
        return a * b**2 / (3 + 1.8 * b / a)


class Circle(cross_section):
    def __init__(self, radius: float):
        self.radius = radius

    @property
    def area(self):
        return math.pi * self.radius**2

    @property
    def Iyy(self):
        return math.pi * self.radius**4 / 4

    @property
    def Izz(self):
        return math.pi * self.radius**4 / 4

    @property
    def CoG_y(self):
        return self.radius

    @property
    def CoG_z(self):
        return self.radius

    @property
    def J_torsion(self):
        return math.pi * self.radius**4 / 2  # Torsional constant for circular section

    @property
    def W_torsion(self):
        return self.J_torsion / self.radius  # Torsional section modulus for circular section


class Hollow_Circle(cross_section):
    def __init__(self, outer_radius: float, inner_radius: float):
        self.outer_radius = outer_radius
        self.inner_radius = inner_radius

    @property
    def area(self):
        return math.pi * (self.outer_radius**2 - self.inner_radius**2)

    @property
    def A_enclosed(self):  # Area enclosed by the wall mid-line (Bredt)
        return math.pi * ((self.inner_radius + self.outer_radius) / 2)**2

    @property
    def Iyy(self):
        return math.pi / 4 * (self.outer_radius**4 - self.inner_radius**4)

    @property
    def Izz(self):
        return math.pi / 4 * (self.outer_radius**4 - self.inner_radius**4)

    @property
    def CoG_y(self):
        return self.outer_radius

    @property
    def CoG_z(self):
        return self.outer_radius

    @property
    def J_torsion(self):
        return math.pi / 2 * (self.outer_radius**4 - self.inner_radius**4)  # Torsional constant for hollow circular section

    @property
    def W_torsion(self):
        return self.J_torsion / self.outer_radius  # Torsional section modulus for hollow circular section


class Rectangular_Tube(cross_section):
    def __init__(self, outer_width, outer_height, wall_thickness):
        self.outer_width = outer_width
        self.outer_height = outer_height
        self.wall_thickness = wall_thickness

    @property
    def A_enclosed(self):  # Area enclosed by the wall mid-line (Bredt)
        t = self.wall_thickness
        return (self.outer_width - t) * (self.outer_height - t)

    @property
    def area(self):
        iw = self.outer_width - 2 * self.wall_thickness
        ih = self.outer_height - 2 * self.wall_thickness
        return self.outer_width * self.outer_height - iw * ih

    @property
    def Iyy(self):
        iw = self.outer_width - 2 * self.wall_thickness
        ih = self.outer_height - 2 * self.wall_thickness
        return (self.outer_width * self.outer_height**3 -
                iw * ih**3) / 12

    @property
    def Izz(self):
        iw = self.outer_width - 2 * self.wall_thickness
        ih = self.outer_height - 2 * self.wall_thickness
        return (self.outer_height * self.outer_width**3 -
                ih * iw**3) / 12

    @property
    def CoG_y(self):
        return self.outer_height / 2

    @property
    def CoG_z(self):
        return self.outer_width / 2

    def warping_free(self):
        # Constant wall thickness and material: warping-free only when square
        return self.outer_width == self.outer_height

    @property
    def J_torsion(self):
        # Bredt's second formula with constant wall thickness: 4 A_m^2 / (s / t)
        t = self.wall_thickness
        perimeter = 2 * ((self.outer_width - t) + (self.outer_height - t))
        return 4 * self.A_enclosed**2 * t / perimeter

    @property
    def W_torsion(self):
        # Bredt's first formula: tau_max = T / (2 A_m t_min)
        return 2 * self.A_enclosed * self.wall_thickness

# ----------- OPEN PROFILES ---------------------------
# fw = flange width, ft = flange thickness, wh = clear web height between
# flanges, wt = web thickness.

class I_beam(cross_section):
    def __init__(self, flange_width, flange_thickness, web_height, web_thickness):
        self.fw = flange_width
        self.ft = flange_thickness
        self.wh = web_height
        self.wt = web_thickness

    @property
    def area(self):
        return 2 * self.fw * self.ft + self.wh * self.wt

    @property
    def Iyy(self):
        return (2 * self.fw * self.ft**3 + self.wt * self.wh**3) / 12 + 2 * self.fw * self.ft * (self.wh/2 + self.ft/2)**2

    @property
    def Izz(self):
        return (2 * self.ft * self.fw**3 + self.wh * self.wt**3) / 12

    @property
    def CoG_y(self):
        return self.wh / 2 + self.ft

    @property
    def CoG_z(self):
        return self.fw / 2

    @property
    def J_torsion(self):
        # Thin-walled open section sum(b t^3 / 3) with 1.3 correction for fillets
        return (2 * self.ft**3 * self.fw + self.wh * self.wt**3) * 1.3 / 3

    @property
    def W_torsion(self):
        return self.J_torsion / max(self.ft, self.wt)  # Torsional section modulus for I-beam

    @property
    def Iy_flange(self):  # One flange about the web axis
        return (self.ft * self.fw**3) / 12

    @property
    def C_torsion(self):  # Warping constant: I_flange * h^2 / 2, h = distance between flange centroids
        h = self.wh + self.ft
        return self.Iy_flange * h**2 / 2

class H_beam(I_beam):
    pass


class T_beam(cross_section):
    """Flange on top, web below."""

    def __init__(self, flange_width, flange_thickness, web_height, web_thickness):
        self.fw = flange_width
        self.ft = flange_thickness
        self.wh = web_height
        self.wt = web_thickness

    @property
    def A_flange(self):
        return self.fw * self.ft

    @property
    def A_web(self):
        return self.wh * self.wt

    @property
    def area(self):
        return self.A_flange + self.A_web

    @property
    def CoG_y(self):
        y_flange = self.wh + self.ft / 2
        y_web = self.wh / 2
        return (self.A_flange * y_flange + self.A_web * y_web) / self.area

    @property
    def CoG_z(self):
        return self.fw / 2

    @property
    def Iyy(self):
        y = self.CoG_y
        return (self.fw * self.ft**3 / 12 + self.A_flange * (self.wh + self.ft/2 - y)**2
                + self.wt * self.wh**3 / 12 + self.A_web * (self.wh/2 - y)**2)

    @property
    def Izz(self):
        return (self.ft * self.fw**3 + self.wh * self.wt**3) / 12

    @property
    def CoS_y(self):  # Shear centre at the flange/web intersection
        return self.wh + self.ft / 2

    @property
    def J_torsion(self):
        return (self.fw * self.ft**3 + self.wh * self.wt**3) * 1.12 / 3

    @property
    def W_torsion(self):
        return self.J_torsion / max(self.ft, self.wt)  # Torsional section modulus for T-beam


class C_beam(cross_section):
    """Channel: web on the left, both flanges pointing right."""

    def __init__(self, flange_width, flange_thickness, web_height, web_thickness):
        self.fw = flange_width
        self.ft = flange_thickness
        self.wh = web_height
        self.wt = web_thickness

    @property
    def A_flange(self):
        return self.fw * self.ft

    @property
    def A_web(self):
        return self.wh * self.wt

    @property
    def area(self):
        return 2 * self.A_flange + self.A_web

    @property
    def CoG_y(self):
        return self.wh / 2 + self.ft

    @property
    def CoG_z(self):
        return (2 * self.A_flange * self.fw / 2 + self.A_web * self.wt / 2) / self.area

    @property
    def Iyy(self):
        return (2 * self.fw * self.ft**3 + self.wt * self.wh**3) / 12 + 2 * self.A_flange * (self.wh/2 + self.ft/2)**2

    @property
    def Izz(self):  # About the vertical axis through the centroid
        z = self.CoG_z
        return (2 * (self.ft * self.fw**3 / 12 + self.A_flange * (self.fw/2 - z)**2)
                + self.wh * self.wt**3 / 12 + self.A_web * (z - self.wt/2)**2)

    @property
    def shear_centre_offset(self):
        # Distance of the shear centre from the web mid-line, on the side away
        # from the flanges (thin-walled): e = 3 b^2 tf / (6 b tf + h tw)
        b = self.fw - self.wt / 2
        h = self.wh + self.ft
        return 3 * b**2 * self.ft / (6 * b * self.ft + h * self.wt)

    @property
    def CoS_z(self):
        return self.wt / 2 - self.shear_centre_offset

    @property
    def J_torsion(self):
        # Approximate torsional constant for C-beam
        return (2 * self.ft**3 * self.fw + self.wh * self.wt**3) * 1.12 / 3

    @property
    def W_torsion(self):
        return self.J_torsion / max(self.ft, self.wt)  # Torsional section modulus for C-beam

    @property
    def C_torsion(self):  # Warping constant, b and h measured to wall mid-lines
        b = self.fw - self.wt / 2
        h = self.wh + self.ft
        Af, Aw = b * self.ft, h * self.wt
        return h**2 * b**2 * Af * (1/6 - Af / (8 * Af + 4/3 * Aw))


class Z_beam(cross_section):
    """Z-section: top flange to the right, bottom flange to the left (point symmetric)."""

    def __init__(self, flange_width, flange_thickness, web_height, web_thickness):
        self.fw = flange_width
        self.ft = flange_thickness
        self.wh = web_height
        self.wt = web_thickness

    @property
    def A_flange(self):
        return self.fw * self.ft

    @property
    def A_web(self):
        return self.wh * self.wt

    @property
    def area(self):
        return 2 * self.A_flange + self.A_web

    @property
    def CoG_y(self):
        return self.wh / 2 + self.ft

    @property
    def CoG_z(self):
        return self.fw - self.wt / 2  # Bounding box width is 2*fw - wt

    @property
    def _flange_offsets(self):
        d = self.wh / 2 + self.ft / 2      # vertical, flange centroid to section centroid
        e = self.fw / 2 - self.wt / 2      # horizontal, flange centroid to section centroid
        return d, e

    @property
    def Iyy(self):
        d, _ = self._flange_offsets
        return (2 * self.fw * self.ft**3 + self.wt * self.wh**3) / 12 + 2 * self.A_flange * d**2

    @property
    def Izz(self):
        _, e = self._flange_offsets
        return (2 * self.ft * self.fw**3 + self.wh * self.wt**3) / 12 + 2 * self.A_flange * e**2

    @property
    def Iyz(self):
        # Top flange at (+e, +d), bottom at (-e, -d): non-zero product of inertia
        d, e = self._flange_offsets
        return -2 * self.A_flange * d * e

    @property
    def J_torsion(self):
        # Approximate torsional constant for Z-beam
        return (2 * self.ft**3 * self.fw + self.wh * self.wt**3) * 1.12 / 3

    @property
    def W_torsion(self):
        return self.J_torsion / max(self.ft, self.wt)  # Torsional section modulus for Z-beam

    @property
    def C_torsion(self):  # Warping constant, b and h measured to wall mid-lines
        b = self.fw - self.wt / 2
        h = self.wh + self.ft
        Af, Aw = b * self.ft, h * self.wt
        return h**2 * b**2 * Af * (1/6 - Af / (8 * Af + 4 * Aw))


class L_beam(cross_section):
    """Equal-leg angle, corner at the bottom-left."""

    def __init__(self, leg_length, leg_thickness):
        self.leg_length = leg_length
        self.leg_thickness = leg_thickness

    @property
    def area(self):
        return 2 * self.leg_length * self.leg_thickness - self.leg_thickness**2

    @property
    def CoG_y(self):
        L, t = self.leg_length, self.leg_thickness
        return (L**2 + L * t - t**2) / (2 * (2 * L - t))

    @property
    def CoG_z(self):
        return self.CoG_y

    @property
    def Iyy(self):  # About the centroidal axis parallel to a leg
        L, t, c = self.leg_length, self.leg_thickness, self.CoG_y
        return (t * (L - c)**3 + L * c**3 - (L - t) * (c - t)**3) / 3

    @property
    def Izz(self):
        return self.Iyy

    @property
    def Iyz(self):
        # Sum of A * dy * dz for the two leg rectangles about the centroid
        L, t, c = self.leg_length, self.leg_thickness, self.CoG_y
        A_v, A_h = L * t, (L - t) * t  # vertical leg, horizontal leg without the corner
        vertical = A_v * (t/2 - c) * (L/2 - c)
        horizontal = A_h * (t + (L - t)/2 - c) * (t/2 - c)
        return vertical + horizontal

    @property
    def CoS_y(self):  # Shear centre at the intersection of the leg mid-lines
        return self.leg_thickness / 2

    @property
    def CoS_z(self):
        return self.leg_thickness / 2

    @property
    def J_torsion(self):
        return (2 * self.leg_length - self.leg_thickness) * self.leg_thickness**3 / 3

    @property
    def W_torsion(self):
        return self.J_torsion / self.leg_thickness  # Torsional section modulus for L-beam


# =========================================================
# BEAM OBJECT
# =========================================================

class beam:
    def __init__(self, material, length, shape: cross_section):
        self.material = material
        self.E = material.E
        self.rho = material.rho
        self.shape = shape
        self.loads = []
        self.left_end = None
        self.right_end = None

        # Specific properties for performance metrics
        self.specific_axial_strength = material.ultimate_strength / material.rho if material.ultimate_strength and material.rho else None
        self.specific_bending_strength = material.yield_strength**(2/3) / material.rho if material.yield_strength and material.rho else None
        self.specific_bending_stiffness = material.E / material.rho if material.E and material.rho else None
        self.specific_buckling_stiffness = material.E**0.5 / material.rho if material.E and material.rho else None
        self.length = length

    def set_end_conditions(self, left, right):
        self.left_end = left
        self.right_end = right

    def add_load(self, load):
        self.loads.append(load)

    def get_mass(self):  # kg
        return self.shape.area * self.length * self.rho

class plate(beam):
    def __init__(self, material, length, width, thickness):
        shape = Rectangle(width, thickness)
        super().__init__(material, length, shape)
        self.specific_bending_strength = material.yield_strength**(1/2) / material.rho if material.yield_strength and material.rho else None
        self.specific_bending_stiffness = material.E**0.5 / material.rho if material.E and material.rho else None
        self.specific_buckling_stiffness = material.E**(1/3) / material.rho if material.E and material.rho else None

class rod(beam):
    def __init__(self, material, length, diameter):
        shape = Circle(diameter/2)
        super().__init__(material, length, shape)
        self.specific_bending_strength = material.yield_strength**(3/2) / material.rho if material.yield_strength and material.rho else None
        self.specific_bending_stiffness = material.E**(1/3) / material.rho if material.E and material.rho else None
