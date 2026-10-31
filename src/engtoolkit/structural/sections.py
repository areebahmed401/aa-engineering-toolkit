"""
Cross-sections and structural members.

Units: SI throughout (m, m², m⁴, kg/m³).

Axis convention for every cross-section:
- y-axis : horizontal, bending about y is the "strong axis" bending (Iyy)
- z-axis : vertical
- Positions (CoG_*, CoS_*) are measured from the bottom-left corner of the
  section's bounding box: *_y is the vertical position, *_z the horizontal one.
- ``outline()`` returns the shape as polygons in the same (horizontal, vertical) coordinates.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

from engtoolkit.core.results import Result, rfield
from engtoolkit.materials import Material, get_material

Point = tuple[float, float]


def _rect(z0: float, y0: float, w: float, h: float) -> list[Point]:
    return [(z0, y0), (z0 + w, y0), (z0 + w, y0 + h), (z0, y0 + h)]


def _circle(zc: float, yc: float, r: float, n: int = 72) -> list[Point]:
    return [(zc + r * math.cos(2 * math.pi * i / n), yc + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


@dataclass
class SectionProperties(Result):
    shape: str = rfield("", "Shape")
    area: float = rfield("m^2", "Area A")
    Iyy: float = rfield("m^4", "Second moment Iyy (strong axis)")
    Izz: float = rfield("m^4", "Second moment Izz (weak axis)")
    Iyz: float = rfield("m^4", "Product of inertia Iyz")
    Ip: float = rfield("m^4", "Polar moment Ip")
    W_el_y: float = rfield("m^3", "Elastic section modulus Wy")
    r_y: float = rfield("m", "Radius of gyration ry")
    J_torsion: float = rfield("m^4", "Torsion constant J")
    W_torsion: float = rfield("m^3", "Torsional section modulus Wt")
    C_warping: float = rfield("m^6", "Warping constant Cw")
    height: float = rfield("m", "Height")
    width: float = rfield("m", "Width")
    CoG_y: float = rfield("m", "Centroid height from bottom")
    CoG_z: float = rfield("m", "Centroid from left edge")
    CoS_y: float = rfield("m", "Shear centre height from bottom")
    CoS_z: float = rfield("m", "Shear centre from left edge")
    mass_per_m: float = rfield("kg/m", "Mass per metre (steel)")


# =========================================================
# 1. CROSS-SECTION BASE CLASS
# =========================================================

class CrossSection(ABC):

    @property
    @abstractmethod
    def area(self) -> float: ...

    @property
    @abstractmethod
    def Iyy(self) -> float: ...

    @property
    @abstractmethod
    def Izz(self) -> float: ...

    @property
    @abstractmethod
    def height(self) -> float: ...

    @property
    @abstractmethod
    def width(self) -> float: ...

    @abstractmethod
    def outline(self) -> dict[str, list]:
        """{'outer': [points], 'holes': [[points], ...]} in (horizontal, vertical) metres."""

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

    @property
    def CoG_y(self) -> float:
        return self.height / 2

    @property
    def CoG_z(self) -> float:
        return self.width / 2

    # Shear centre defaults to the centroid (doubly symmetric sections)
    @property
    def CoS_y(self) -> float:
        return self.CoG_y

    @property
    def CoS_z(self) -> float:
        return self.CoG_z

    @property
    def c_top(self) -> float:
        """Distance from the centroid to the top fibre [m]."""
        return self.height - self.CoG_y

    @property
    def c_bottom(self) -> float:
        return self.CoG_y

    @property
    def W_el_y(self) -> float:
        """Elastic section modulus about y (governing, i.e. smallest) [m³]."""
        return self.Iyy / max(self.c_top, self.c_bottom)

    @property
    def C_torsion(self) -> float:  # warping constant; ~0 for closed and solid sections
        return 0.0

    # Old spelling aliases for torsion properties
    @property
    def J_Torsion(self) -> float:
        return self.J_torsion

    @property
    def W_Torsion(self) -> float:
        return self.W_torsion

    def properties(self, rho: float = 7850.0) -> SectionProperties:
        return SectionProperties(
            shape=type(self).__name__, area=self.area, Iyy=self.Iyy, Izz=self.Izz, Iyz=self.Iyz, Ip=self.Ip,
            W_el_y=self.W_el_y, r_y=self.Rg, J_torsion=self.J_torsion, W_torsion=self.W_torsion,
            C_warping=self.C_torsion, height=self.height, width=self.width, CoG_y=self.CoG_y, CoG_z=self.CoG_z,
            CoS_y=self.CoS_y, CoS_z=self.CoS_z, mass_per_m=self.area * rho,
        )


# =========================================================
# 2. CROSS-SECTION IMPLEMENTATIONS
# =========================================================

#---------- SOLID AND CLOSED PROFILES -------------------

class Rectangle(CrossSection):
    def __init__(self, width: float, height: float):
        self._w = width
        self._h = height

    width = property(lambda self: self._w)
    height = property(lambda self: self._h)

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
    def J_torsion(self):
        # Saint-Venant torsion constant, a = long side, b = short side (Roark)
        a, b = max(self.width, self.height), min(self.width, self.height)
        return a * b**3 * (1/3 - 0.21 * (b/a) * (1 - b**4 / (12 * a**4)))

    @property
    def W_torsion(self):
        # Torsional section modulus, tau_max = T / W_t (Roark)
        a, b = max(self.width, self.height), min(self.width, self.height)
        return a * b**2 / (3 + 1.8 * b / a)

    def outline(self):
        return {"outer": _rect(0, 0, self.width, self.height), "holes": []}


class Circle(CrossSection):
    def __init__(self, radius: float):
        self.radius = radius

    height = property(lambda self: 2 * self.radius)
    width = property(lambda self: 2 * self.radius)

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
    def J_torsion(self):
        return math.pi * self.radius**4 / 2  # Torsional constant for circular section

    @property
    def W_torsion(self):
        return self.J_torsion / self.radius  # Torsional section modulus for circular section

    def outline(self):
        return {"outer": _circle(self.radius, self.radius, self.radius), "holes": []}


class HollowCircle(CrossSection):
    def __init__(self, outer_radius: float, inner_radius: float):
        if inner_radius >= outer_radius:
            raise ValueError("Inner radius must be smaller than outer radius")
        self.outer_radius = outer_radius
        self.inner_radius = inner_radius

    height = property(lambda self: 2 * self.outer_radius)
    width = property(lambda self: 2 * self.outer_radius)

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
        return self.Iyy

    @property
    def J_torsion(self):
        return math.pi / 2 * (self.outer_radius**4 - self.inner_radius**4)  # Torsional constant for hollow circular section

    @property
    def W_torsion(self):
        return self.J_torsion / self.outer_radius  # Torsional section modulus for hollow circular section

    def outline(self):
        r = self.outer_radius
        return {"outer": _circle(r, r, r), "holes": [_circle(r, r, self.inner_radius)]}


class RectangularTube(CrossSection):
    def __init__(self, outer_width, outer_height, wall_thickness):
        if 2 * wall_thickness >= min(outer_width, outer_height):
            raise ValueError("Wall thickness too large for the outer dimensions")
        self.outer_width = outer_width
        self.outer_height = outer_height
        self.wall_thickness = wall_thickness

    width = property(lambda self: self.outer_width)
    height = property(lambda self: self.outer_height)

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
        return (self.outer_width * self.outer_height**3 - iw * ih**3) / 12

    @property
    def Izz(self):
        iw = self.outer_width - 2 * self.wall_thickness
        ih = self.outer_height - 2 * self.wall_thickness
        return (self.outer_height * self.outer_width**3 - ih * iw**3) / 12

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

    def outline(self):
        t = self.wall_thickness
        return {"outer": _rect(0, 0, self.outer_width, self.outer_height),
                "holes": [_rect(t, t, self.outer_width - 2 * t, self.outer_height - 2 * t)]}


def SquareTube(outer_width: float, wall_thickness: float) -> RectangularTube:
    return RectangularTube(outer_width, outer_width, wall_thickness)


# ----------- OPEN PROFILES ---------------------------
# fw = flange width, ft = flange thickness, wh = clear web height between
# flanges, wt = web thickness.

class _FlangedSection(CrossSection):
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


class IBeam(_FlangedSection):
    height = property(lambda self: self.wh + 2 * self.ft)
    width = property(lambda self: self.fw)

    @classmethod
    def from_profile(cls, designation: str) -> "IBeam":
        """Build from a catalog profile, e.g. IBeam.from_profile('IPE 200') (root radii ignored)."""
        from engtoolkit.catalogs import get_profile
        p = get_profile(designation)
        section = cls(p.b, p.tf, p.web_height, p.tw)
        section.designation = p.designation
        return section

    @property
    def area(self):
        return 2 * self.A_flange + self.A_web

    @property
    def Iyy(self):
        return (2 * self.fw * self.ft**3 + self.wt * self.wh**3) / 12 + 2 * self.A_flange * (self.wh/2 + self.ft/2)**2

    @property
    def Izz(self):
        return (2 * self.ft * self.fw**3 + self.wh * self.wt**3) / 12

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

    def outline(self):
        fw, ft, wh, wt = self.fw, self.ft, self.wh, self.wt
        zw = (fw - wt) / 2
        H = self.height
        return {"outer": [(0, 0), (fw, 0), (fw, ft), (zw + wt, ft), (zw + wt, ft + wh), (fw, ft + wh),
                          (fw, H), (0, H), (0, ft + wh), (zw, ft + wh), (zw, ft), (0, ft)], "holes": []}


class HBeam(IBeam):
    pass


class TBeam(_FlangedSection):
    """Flange on top, web below."""

    height = property(lambda self: self.wh + self.ft)
    width = property(lambda self: self.fw)

    @property
    def area(self):
        return self.A_flange + self.A_web

    @property
    def CoG_y(self):
        y_flange = self.wh + self.ft / 2
        y_web = self.wh / 2
        return (self.A_flange * y_flange + self.A_web * y_web) / self.area

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

    def outline(self):
        zw = (self.fw - self.wt) / 2
        return {"outer": [(zw, 0), (zw + self.wt, 0), (zw + self.wt, self.wh), (self.fw, self.wh),
                          (self.fw, self.height), (0, self.height), (0, self.wh), (zw, self.wh)], "holes": []}


class CBeam(_FlangedSection):
    """Channel: web on the left, both flanges pointing right."""

    height = property(lambda self: self.wh + 2 * self.ft)
    width = property(lambda self: self.fw)

    @property
    def area(self):
        return 2 * self.A_flange + self.A_web

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

    def outline(self):
        H = self.height
        return {"outer": [(0, 0), (self.fw, 0), (self.fw, self.ft), (self.wt, self.ft), (self.wt, H - self.ft),
                          (self.fw, H - self.ft), (self.fw, H), (0, H)], "holes": []}


class ZBeam(_FlangedSection):
    """Z-section: top flange to the right, bottom flange to the left (point symmetric)."""

    height = property(lambda self: self.wh + 2 * self.ft)
    width = property(lambda self: 2 * self.fw - self.wt)

    @property
    def area(self):
        return 2 * self.A_flange + self.A_web

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

    def outline(self):
        z0 = self.fw - self.wt  # web left edge
        H = self.height
        return {"outer": [(0, 0), (self.fw, 0), (self.fw, self.ft + self.wh), (self.width, self.ft + self.wh),
                          (self.width, H), (z0, H), (z0, self.ft), (0, self.ft)], "holes": []}


class LBeam(CrossSection):
    """Equal-leg angle, corner at the bottom-left."""

    def __init__(self, leg_length, leg_thickness):
        self.leg_length = leg_length
        self.leg_thickness = leg_thickness

    height = property(lambda self: self.leg_length)
    width = property(lambda self: self.leg_length)

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

    def outline(self):
        L, t = self.leg_length, self.leg_thickness
        return {"outer": [(0, 0), (L, 0), (L, t), (t, t), (t, L), (0, L)], "holes": []}


# =========================================================
# BEAM OBJECT
# =========================================================

class Beam:
    def __init__(self, material: str | Material, length: float, shape: CrossSection):
        material = get_material(material)
        self.material = material
        self.E = material.E
        self.rho = material.rho
        self.shape = shape
        self.loads = []
        self.left_end = None
        self.right_end = None
        self.length = length

        # Specific properties for performance metrics (lightweighting criteria)
        sy, su, E, rho = material.yield_strength, material.ultimate_strength, material.E, material.rho
        self.specific_axial_strength = su / rho if su and rho else None
        self.specific_bending_strength = sy**(2/3) / rho if sy and rho else None
        self.specific_bending_stiffness = E / rho if E and rho else None
        self.specific_buckling_stiffness = E**0.5 / rho if E and rho else None

    def set_end_conditions(self, left, right):
        self.left_end = left
        self.right_end = right

    def add_load(self, load):
        self.loads.append(load)

    def get_mass(self):  # kg
        return self.shape.area * self.length * self.rho


class Plate(Beam):
    def __init__(self, material, length, width, thickness):
        super().__init__(material, length, Rectangle(width, thickness))
        m = self.material
        sy, E, rho = m.yield_strength, m.E, m.rho
        self.specific_bending_strength = sy**(1/2) / rho if sy and rho else None
        self.specific_bending_stiffness = E**0.5 / rho if E and rho else None
        self.specific_buckling_stiffness = E**(1/3) / rho if E and rho else None


class Rod(Beam):
    def __init__(self, material, length, diameter):
        super().__init__(material, length, Circle(diameter/2))
        m = self.material
        sy, E, rho = m.yield_strength, m.E, m.rho
        self.specific_bending_strength = sy**(3/2) / rho if sy and rho else None
        self.specific_bending_stiffness = E**(1/3) / rho if E and rho else None


# Original names, kept so earlier notebooks keep working
cross_section = CrossSection
Hollow_Circle = HollowCircle
Rectangular_Tube = RectangularTube
I_beam = IBeam
H_beam = HBeam
T_beam = TBeam
C_beam = CBeam
Z_beam = ZBeam
L_beam = LBeam
beam = Beam
plate = Plate
rod = Rod
