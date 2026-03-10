from beams import beam, Rectangle
from materials import get_material
from FBD_beams import *
from solvers import DeterminateSolver

# 1. Beam and material
shape = Rectangle(width=0.1, height=0.2)
material = get_material("Steel")
b = beam(material=material, length=2.0, shape=shape)

# Assume you already have a beam object from your beam.py
from FBD_beams import PointLoad, DistributedLoad, Pinned, Roller

# Define beam ends
b.set_end_conditions(left=Pinned(), right=Roller())

# Add loads
b.add_load(PointLoad(P=10e3, x=1.0))
b.add_load(DistributedLoad(w=2e3, x1=0, x2=1.0))
b.add_load(MomentLoad(M=5e3, x=1.5))

# fbd = plot_fbd(b)
# Solve statically determinate
solver = DeterminateSolver(b)
print("Reactions:", solver.reactions())

# Plot diagrams
solver.plot()