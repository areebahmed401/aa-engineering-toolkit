# Structural

Sections, beams, determinacy, FEM and torsion. SI units (m, N, Pa).

::: engtoolkit.structural.sections

::: engtoolkit.structural.loads

::: engtoolkit.structural.analysis

::: engtoolkit.structural.determinate

::: engtoolkit.structural.fem

::: engtoolkit.structural.torsion

## Shear flow (thin-walled)

Tool `structural.shear_flow`, solver `engtoolkit.structural.thin_walled.shear_flow`. Follows the RWTH OLS
formulary (§2) and its notation.

- **Model**: straight walls (mid-lines) between nodes; open, branched, closed and multi-cell sections.
  Wall i → j defines the arc length s and the positive sign of the shear flow t [N/m].
- **Axes**: x1 beam axis, x2 horizontal (right), x3 vertical pointing **down**. Q2, Q3 positive in +x2, +x3.
  M_t positive about +x1 (right-handed x1, x2, x3, i.e. turning from x2 towards x3).
- **Properties** about the centroid along the mid-lines only (no h³ own terms): A = Σ h l,
  J22 = ∫x3² h ds, J33 = ∫x2² h ds, J23 = ∫x2 x3 h ds, principal angle tan 2φ = −2 J23/(J22 − J33).
- **Cut-open flow**: each cell is cut once (at the start of a wall outside a spanning tree);
  t' = −[(Q3 J33 − Q2 J23) S2 + (Q2 J22 − Q3 J23) S3]/(J22 J33 − J23²) with S2 = ∫x3 h ds, S3 = ∫x2 h ds,
  continuous at the nodes (Σ in = Σ out, t = 0 at free ends). With J23 = 0 this is t' = −Q3 S2/J22 − Q2 S3/J33.
- **Closing flows**: one circulating t0 per cell (positive from x2 towards x3) from ϑ' = 0,
  ∮ (t' + t0)/(G h) ds = 0 per cell; walls shared by two cells carry the difference of their t0.
- **Shear centre** from moment equilibrium of t' + t0 for unit Q3 (x2 position) and unit Q2 (x3 position).
- **Torque** about SC = M_t + moment of (Q2, Q3) at (a2, a3) about SC. Closed sections carry it with Bredt
  flows (single cell M_t = 2 A t0; multi-cell with equal rate of twist in every cell). Open sections carry it
  by Saint-Venant shear: J_T = Σ l h³/3 and τ = M_t h_max/J_T are reported separately and not added to t.
- **Limits**: thin walls (h ≪ section size), straight walls, linear elastic, no warping restraint; open
  branches attached to closed cells carry no torque; walls must not cross without a shared node.
