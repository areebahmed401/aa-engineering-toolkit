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

## Torsion (free and restrained warping)

Tool `structural.torsion`, solver `engtoolkit.structural.torsion.solve_torsion`, sectorial coordinate
`engtoolkit.structural.thin_walled.sectorial`. Follows the RWTH OLS formulary (§3) and its notation: x1 beam
axis, T torque about the shear centre (positive about +x1), ϑ twist, ϑ' = dϑ/dx1.

- **Free warping (Saint-Venant, §3.1)**: T = G J_T ϑ', τ_max = T/W_T.
  - Solid circle J_T = πR⁴/2, W_T = πR³/2; ellipse (semi-axes a ≥ b) J_T = π a³b³/(a² + b²), W_T = π a b²/2.
  - Solid rectangle B × H (B short side): J_T = η1 B³H/3, W_T = η2 B²H/3, with η1, η2 from the exact
    Saint-Venant series (they reproduce the formulary table, e.g. H/B = 1: 0.4217, 0.6245).
  - Open thin-walled shapes: J_T = η3/3 Σ h³ l, W_T = J_T/h_max with η3 = 0.99 (L), 1.12 (C, Z, T), 1.30 (I);
    a drawn open section uses the η3 input (default 1.0).
  - Closed thin-walled: Bredt J_T = 4A²/∮ds/h, W_T = 2 A h_min (drawn sections: multi-cell Bredt from the
    shear-flow solver, W_T = T/τ_max from the cell flows). Hollow circle: exact π(R⁴ − r⁴)/2.
  - Rectangular tube as a thick-walled hollow rectangle: common ϑ', J_T = J_TB (Bredt, mid-line box) + Σ J_Ti
    (each wall as a solid rectangle), torque split by stiffness, τ_max = max_i(τ_Bi + τ_i,max), W_T = T/τ_max.
    For thin walls this tends to Bredt.
- **Restrained warping (§3.2)**: E C_T ϑ'''' − G J_T ϑ'' = m_t with ξ = x/L, α² = G J_T L²/(E C_T),
  μ = T L³/(E C_T); T = M_SV + M_B, M_SV = G J_T ϑ', M_B = −E C_T ϑ''', dT/dx1 = −m_t; bimoment
  B = −E C_T ϑ'', warping stress σ_ω = B ω/C_T (reported with ω_max), τ_SV = |M_SV|/W_T.
  - Exact piecewise solution between point torques, assembled into one linear system (continuity of ϑ, ϑ', ϑ''
    and a jump −T_k of the internal torque at each point torque); exponential basis for large α, so it works
    up to α ~ 10³ and beyond and approaches Saint-Venant.
  - Supports per end: fixed (ϑ = ϑ' = 0), fork (ϑ = ϑ'' = 0), free (ϑ'' = 0, end torque). At least one end must
    hold ϑ. Loads: point torques (x, T) and one uniform m_t over the span; with no point torques the legacy
    `torque` acts at x = L (the old cantilever payload gives the formulary closed form, class `Torsion`).
  - C_T = 0 (closed and solid sections): restrained = free; the same supports with G J_T ϑ'' = −m_t.
  - Mode "free" solves Saint-Venant only (also for open sections). A transverse force (Q2, Q3) at x = L whose
    load line is offset from the shear centre adds T = Q2 e3 − Q3 e2 at x = L, with e = shear centre − load line.
- **Warping constant**: C_T = ∫ω² h ds with the principal sectorial coordinate ω (pole at the shear centre,
  ∫ω h ds = 0), computed on the mid-line model of open sections. It equals the formulary formulas: I
  C_T = a² J_F/2, C a²b²A_F(1/6 − A_F/(8A_F + 4/3 A_S)), Z a²b²A_F(1/6 − A_F/(8A_F + 4A_S)); T and L ≈ 0.
- **Limits**: linear elastic, straight prismatic member, constant section; closed sections are treated as
  warping-free (C_T = 0); drawn walls use the material's G.
