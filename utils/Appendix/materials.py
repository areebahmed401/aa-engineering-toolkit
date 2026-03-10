"""
material.py

Essential engineering materials with typical properties,
and functionality to add new materials.
"""

class Material:
    """Generic material class."""
    def __init__(self, name, E, nu, rho, yield_strength, ultimate_strength, roughness=None, thermal_conductivity=None, specific_heat=None):
        """
        Parameters:
        name : str : Material name
        E    : float : Young's modulus [Pa]
        nu   : float : Poisson's ratio [-]
        rho  : float : Density [kg/m³]
        yield_strength  : float : Yield strength [Pa] (optional)
        ultimate_strength  : float : Ultimate strength [Pa] (optional)
        roughness  : float : Surface roughness [m] (optional)
        thermal_conductivity  : float : Thermal conductivity [W/m/K] (optional)
        specific_heat  : float : Specific heat [J/kg/K] (optional)
        """
        self.name = name
        self.E = E
        self.nu = nu
        self.rho = rho
        self.G = E / (2 * (1 + nu))  # Shear modulus
        self.roughness = roughness # m, optional
        self.thermal_conductivity = thermal_conductivity # W/m/K
        self.specific_heat = specific_heat #kJ/kg/K         
        self.yield_strength = yield_strength  # Optional: can be set later
        self.ultimate_strength = ultimate_strength  # Optional: can be set later

# Dictionary to store all materials
_materials = {}

# -------------------- Predefined Materials --------------------
def _add_default_materials():
    add_material("Steel", E=200e9, nu=0.3, rho=7850, yield_strength=250e6, ultimate_strength=400e6)
    add_material("Aluminum", E=70e9, nu=0.3, rho=2700, yield_strength=150e6, ultimate_strength=300e6)
    add_material("CFRP", E=150e9, nu=0.25, rho=1600, yield_strength=600e6, ultimate_strength=800e6)
    add_material("ASTM A106B", E=207e9, nu=0.3, rho=7850, yield_strength=240e6, ultimate_strength=415e6, roughness=4.5e-5, thermal_conductivity=50, specific_heat=480)
    add_material("SS304", E=193e9, nu=0.3, rho=8000, yield_strength=215e6, ultimate_strength=505e6, roughness=1.5e-5, thermal_conductivity=16, specific_heat=500)

# -------------------- Functions --------------------
def add_material(name, E, nu, rho, yield_strength=None, ultimate_strength=None, roughness=None, thermal_conductivity=None, specific_heat=None):
    """Add a new material to the library."""
    _materials[name] = Material(name, E, nu, rho, yield_strength, ultimate_strength, roughness, thermal_conductivity, specific_heat)

def get_material(name):
    """Retrieve a material by name."""
    return _materials.get(name, None)

def list_materials():
    """Return a list of all available material names."""
    return list(_materials.keys())

# Initialize defaults
_add_default_materials()
