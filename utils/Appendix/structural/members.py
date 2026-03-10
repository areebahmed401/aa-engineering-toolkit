from abc import ABC, abstractmethod
import math

# =========================================================
# 1. CROSS-SECTION BASE CLASS
# =========================================================

class cross_section(ABC):

    @property
    @abstractmethod
    def Iyy(self) -> float:
        pass

    @property
    def Rg(self) -> float: # Radius of gyration about x-axis
        return (self.Iy / self.area) ** 0.5
    
    @property
    def CoG_y(self) -> float:
        return 0.0  # Default: symmetric about y-axis
    
    @property
    def CoG_z(self) -> float:
        return 0.0  # Default: symmetric about z-axis
    
    @property
    def CoS_y(self) -> float:
        return 0.0  # Default: symmetric about y-axis
    
    @property
    def CoS_z(self) -> float:
        return 0.0  # Default: symmetric about z-axis
     

# =========================================================
# 2. CROSS-SECTION IMPLEMENTATIONS (RECTANGLE, CIRCLE, I-BEAM, ETC.)
# =========================================================

#---------- CLOSED PROFILES -------------------

class Rectangle(cross_section):
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height

    @property
    def area(self):
        return self.width * self.height

    @property
    def Ix(self):
        return self.width * self.height**3 / 12

    @property
    def Iy(self):
        return self.height * self.width**3 / 12

    @property
    def Iz(self):
        return self.Ix + self.Iy
    
    @property
    def J_Torsion(self):
        N= (16/3) * (1 - 0.63 * (self.height/self.width) * (1 - math.exp(-self.width/self.height))) if self.width > self.height else self.height * self.width**3 * (16/3) * (1 - 0.63 * (self.width/self.height) * (1 - math.exp(-self.height/self.width)))
        # Approximate torsional constant for rectangular section
        return self.width **3 * self.height * N
    
    @property
    def W_Torsion(self):
        return self.J_Torsion()/self.height/2  # Torsional section modulus for rectangular section
    
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
    def J_Torsion(self):
        return math.pi * self.radius**4 / 2  # Torsional constant for circular section
    
    @property
    def W_Torsion(self):
        return self.J_Torsion()/self.radius  # Torsional section modulus for circular section


class Hollow_Circle(cross_section):
    def __init__(self, outer_radius: float, inner_radius: float):
        self.outer_radius = outer_radius
        self.inner_radius = inner_radius

    @property
    def area(self):
        return math.pi * (self.outer_radius**2 - self.inner_radius**2)
    
    @property
    def A_enclosed(self):
        return math.pi * ((self.inner_radius+self.outer_radius)/2)**2

    @property
    def Iyy(self):
        return math.pi / 4 * (self.outer_radius**4 - self.inner_radius**4)

    @property
    def Izz(self):
        return math.pi / 4 * (self.outer_radius**4 - self.inner_radius**4)
    
    @property
    def J_Torsion(self):
        return math.pi / 2 * (self.outer_radius**4 - self.inner_radius**4)  # Torsional constant for hollow circular section
    
    @property
    def W_Torsion(self):
        return self.J_Torsion()/self.outer_radius  # Torsional section modulus for hollow circular section
    
class Rectangular_Tube(cross_section):
    def __init__(self, outer_width, outer_height, wall_thickness):
        self.outer_width = outer_width
        self.outer_height = outer_height
        self.wall_thickness = wall_thickness

    @property
    def A_enclosed(self):
        iw = self.outer_width 
        ih = self.outer_height 
        return iw * ih
    
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
        
    def warping_free(self):
        return True if self.outer_width == self.outer_height else False
    
    @property
    def J_torsion(self):
        return 4*self.A_enclosed**2/(2*(self.outer_width + self.outer_height)/self.wall_thickness)

# ----------- OPEN PROFILES ---------------------------

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
        return (self.fw * self.ft**3 * 2 + self.wh * self.wt**3) / 12 + 2 * self.fw * self.ft * (self.wh/2 + self.ft/2)**2

    @property
    def Izz(self):
        return (self.ft * self.fw**3 * 2 + self.wh * self.wt**3) / 12 
    
    @property
    def J_torsion(self): 
        # Approximate torsional constant for I-beam
        return (2 * self.ft**3 * self.fw + self.wh * self.wt**3) *1.3/ 3
    
    @property
    def W_torsion(self):
        return self.J_Torsion/max(self.ft, self.wt)  # Torsional section modulus for I-beam
    
    @property
    def Iy_flange(self):
        return (self.ft * self.fw**3) / 12 

    @property
    def C_torsion(self): # Torsional bending resistance
        c= self.wh**2 *self.Iy_flange**2/(2*self.Iy_flange)
        return c

class H_beam(I_beam):
    pass


class T_beam(cross_section):
    def __init__(self, flange_width, flange_thickness, web_height, web_thickness):
        self.fw = flange_width
        self.ft = flange_thickness
        self.wh = web_height
        self.wt = web_thickness

    @property
    def area(self):
        return self.fw * self.ft + self.wh * self.wt

    @property
    def Iyy(self):
        return (self.fw * self.ft**3 + self.wh * self.wt**3) / 12 + self.fw * self.ft * (self.wh/2 + self.ft/2)**2

    @property
    def Izz(self):
        return (self.ft * self.fw**3 + self.wh * self.wt**3) / 12
    
    def CoG_y(self):
        A_flange = self.fw * self.ft
        A_web = self.wh * self.wt
        y_flange = self.wh + self.ft / 2
        y_web = self.wh / 2
        return (A_flange * y_flange + A_web * y_web) / (A_flange + A_web)
    
    def CoG_z(self):
        return self.fw / 2  # Assuming symmetric about -axis
    
    def CoS_z(self):
        return self.wh/2-self.CoG_z
    
    @property
    def J_torsion(self): 
        # Approximate torsional constant for I-beam
        return (2 * self.ft**3 * self.fw + self.wh * self.wt**3) *1.12/ 3
    
    @property
    def W_torsion(self):
        return self.J_Torsion()/max(self.ft, self.wt)  # Torsional section modulus for I-beam
    
class C_beam(cross_section):
    def __init__(self, flange_width, flange_thickness, web_height, web_thickness):
        self.fw = flange_width
        self.ft = flange_thickness
        self.wh = web_height
        self.wt = web_thickness

    @property
    def area(self):
        return self.fw * self.ft + self.wh * self.wt
    
    @property
    def A_flange(self):
        return self.fw * self.ft
    
    @property
    def A_web(self):
        return self.wh * self.wt
    
    def CoG_y(self):
        A_flange = self.fw * self.ft
        A_web = self.wh * self.wt
        y_flange = self.wh + self.ft / 2
        y_web = self.wh / 2
        return (A_flange * y_flange + A_web * y_web) / (A_flange + A_web)
    
    def CoG_z(self):
        return (self.fw - self.wt) / 2  # Assuming symmetric about z-axis
    
    @property
    def Iyy(self):
        return (self.fw * self.ft**3 + self.wh**3 * self.wt) / 12 + 2 * (self.fw * self.ft * (self.wh/2 + self.ft/2)**2)

    @property
    def Izz(self): # Moment of inertia about z-axis for C-beam with refernece to CoGy
        return ((self.ft * self.fw**3 + self.wh * self.wt**3) / 12 + 2 * (self.fw * self.ft * (self.fw/2 - self.CoG_y)**2) + self.wh * self.wt * (self.CoG_y - self.wt/2)**2)
    
    def CoS_y(self):
        e= -(self.wh*self.wh*self.ft*self.fw/(2*self.Iyy)) # Eccentricity of shear center from CoG
        return e
    
    @property
    def J_torsion(self):
        # Approximate torsional constant for C-beam
        return (2 * self.ft**3 * self.fw + self.wh * self.wt**3) *1.12/ 3
    
    @property
    def W_torsion(self):
        return self.J_torsion/max(self.ft, self.wt)  # Torsional section modulus for C-beam
    
    @property
    def C_torsion(self): # Torsional bending resistance
        c= self.wh**2 *self.fw**2*self.A_flange*(1/6-self.A_flange/(8*self.A_flange+4/3*self.A_web))
        return c
    
class Z_beam(cross_section):
    def __init__(self, flange_width, flange_thickness, web_height, web_thickness):
        self.fw = flange_width
        self.ft = flange_thickness
        self.wh = web_height
        self.wt = web_thickness

    @property
    def area(self):
        return (self.fw * self.ft)*2 + self.wh * self.wt

    @property
    def Iyy(self):
        return (self.fw * self.ft**3 + self.wh * self.wt**3) / 12 + 2 * self.fw * self.ft * (self.wh/2 + self.ft/2)**2

    @property
    def Izz(self):
        return (self.ft * self.fw**3 + self.wh * self.wt**3) / 12 + 2 * self.fw * self.ft * (self.fw - self.wt/2)**2
   
    @property
    def CoG_y(self):
        A_flange = self.fw * self.ft
        A_web = self.wh * self.wt
        y_flange = self.wh + self.ft / 2
        y_web = self.wh / 2
        return (A_flange * y_flange + A_web * y_web) / (A_flange + A_web)
    
    @property
    def CoG_z(self):
        return (self.fw - self.wt) / 2  # Assuming symmetric about z-axis
    
    @property
    def CoS_y(self):
        e= -(self.wh*self.wh*self.ft*self.fw/(2*self.Ix)) # Eccentricity of shear center from CoG
        return e
    
    @property
    def J_torsion(self):
        # Approximate torsional constant for Z-beam
        return (2 * self.ft**3 * self.fw + self.wh * self.wt**3) *1.12/ 3
    
    @property
    def W_torsion(self):
        return self.J_Torsion()/max(self.ft, self.wt)  # Torsional section modulus for Z-beam
    
    @property
    def C_torsion(self): # Torsional bending resistance
        c= self.wh**2 *self.fw**2*self.A_flange(1/6-self.A_flange/(8*self.A_flange+4*self.A_web))
        return c
    
class L_beam(cross_section):
    def __init__(self, leg_length, leg_thickness):
        self.leg_length = leg_length
        self.leg_thickness = leg_thickness

    @property
    def area(self):
        return 2 * self.leg_length * self.leg_thickness - self.leg_thickness**2

    @property
    def Ix(self):
        return (self.leg_length * self.leg_thickness**3 + self.leg_length * self.leg_thickness**3) / 12

    @property
    def Iy(self):
        return (self.leg_thickness * self.leg_length**3 + self.leg_thickness * self.leg_length**3) / 12

    @property
    def Iz(self):
        return self.Ix + self.Iy
    
    def CoG_y(self):
        A_leg = self.leg_length * self.leg_thickness
        y_leg = self.leg_length / 2
        return (A_leg * y_leg + A_leg * y_leg) / (A_leg + A_leg)
    
    def CoG_z(self):
        return (self.leg_length - self.leg_thickness) / 2  # Assuming symmetric about z-axis
    
    def CoS_y(self):
        e= -(self.leg_length*self.leg_length*self.leg_thickness*self.leg_length/(2*self.Ix)) # Eccentricity of shear center from CoG
        return e
    
    @property
    def J_torsion(self):
        # Approximate torsional constant for L-beam
        return (self.leg_thickness**3 * self.leg_length + self.leg_thickness**3 * self.leg_length) *0.99/ 3
    
    @property
    def W_torsion(self):
        return self.J_Torsion()/max(self.leg_thickness, self.leg_thickness)  # Torsional section modulus for L-beam
    
    
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
        
    def get_mass(self):
        return self.shape.area * self.length * self.rho/1000**3
    
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