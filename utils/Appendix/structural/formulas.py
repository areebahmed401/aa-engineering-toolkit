# Formulas used in structural analysis and design, including bending, shear, torsion, and deflection calculations. These formulas are essential for engineers to analyze and design structural members effectively.
import math

class Torsion:
    """
    Analyzes warping torsion in structural members using Saint-Venant and warping torsion theory.
    
    Solves the differential equation for a cantilever beam under torsional loading with
    boundary conditions at the fixed and free ends.
    """
    
    def __init__(self, beam, TorsionalMoment, position):
        """
        Initialize a Torsion analysis object.

        Parameters:
        -----------
        beam : Beam
            The structural member to be analyzed.
        TorsionalMoment : float
            The applied torsional moment (N·mm or equivalent).
        position : float
            The position along the beam where the torsional moment is applied.

        Raises:
        -------
        ValueError
            If TorsionalMoment is zero or position is not within beam length.
        """
        if TorsionalMoment == 0:
            raise ValueError("TorsionalMoment cannot be zero")
        if position < 0 or position > beam.length:
            raise ValueError(f"Position must be between 0 and {beam.length}")
            
        self.G = beam.material.G  # Shear modulus
        self.J_t = beam.shape.J_torsion  # Torsional moment of area
        self.L = beam.length  # Length of the member
        self.C_t = beam.shape.C_torsion  # Warping constant
        self.E = beam.material.E  # Young's modulus
        self.T = TorsionalMoment  # Applied torsional moment
        self.x = position  # Position of interest
        
        # Cache computed values to avoid redundant calculations
        self._xi = None
        self._alpha = None
        self._mu = None
        self._A1 = None
        self._A2 = None
        self._A3 = None
        
    @property
    def xi(self):
        """Dimensionless position along beam (0 to 1)."""
        if self._xi is None:
            self._xi = self.x / self.L
        return self._xi

    @property
    def alpha(self):
        """Dimensionless warping parameter."""
        if self._alpha is None:
            self._alpha = math.sqrt(self.G * self.J_t * self.L**2 / (self.C_t * self.E))
        return self._alpha
    
    @property
    def mu(self):
        """Dimensionless torsional moment parameter."""
        if self._mu is None:
            self._mu = self.T * self.L**3 / (self.C_t * self.E)
        return self._mu
    
    @property
    def A1(self):
        """Integration constant A1 for the solution."""
        if self._A1 is None:
            self._A1 = -self.mu * math.tanh(self.alpha) / self.alpha**3
        return self._A1
    
    @property
    def A2(self):
        """Integration constant A2 for the solution."""
        if self._A2 is None:
            self._A2 = -self.A1
        return self._A2
    
    @property
    def A3(self):
        """Integration constant A3 for the solution."""
        if self._A3 is None:
            self._A3 = -self.mu / self.alpha**3
        return self._A3
    
    def theta(self):
        """
        Calculate the angle of twist at the specified position.
        
        Returns:
        --------
        float
            Twist angle (radians).
        """
        return (self.A1 + self.A2 * math.cosh(self.alpha * self.xi) + 
                self.A3 * math.sinh(self.alpha * self.xi) + 
                self.mu * self.xi / self.alpha**2)
    
    def __repr__(self):
        """String representation of the Torsion object."""
        return f"Torsion(T={self.T}, x={self.x}, L={self.L}, θ={self.theta():.6f} rad)"