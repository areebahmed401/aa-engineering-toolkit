# Changelog

All notable changes to AA Engineering Toolkit are recorded here.

The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-11-01

### Added

- Dedicated structural page in the web app: section designer with live drawing, centroid and shear
  centre, and a beam builder with free-body diagram, determinacy verdict, reactions, peak values,
  utilisation and the four diagrams.
- ASME Section VIII Div 1 preliminary vessel sizing (`engtoolkit.asme`): shells, heads, nozzle
  reinforcement, external pressure and hydrotest, with a step-by-step vessel builder page, a worked
  example and an end-to-end test. Allowable stress is a user input; no code tables are reproduced.
- Battery modelling (`engtoolkit.electrical`): 1RC/2RC equivalent circuit, lumped thermal model with
  air or cold-plate cooling, calendar and cycle aging, and optional PyBaMM DFN/SPM models.
- Documentation site at `/docs` (MkDocs) with an API reference and how-to guides for adding a tool,
  a material and a discipline.
- Tag-triggered release workflow that builds the wheel and sdist and publishes a GitHub release
  using the matching changelog section.
- `CONTRIBUTING.md`, issue forms and a pull request template.

### Changed

- New gold, black and white truss logo and theme on grey backgrounds.
- Notebooks are frozen ahead of deprecation; new work goes into the package and web app.

### Fixed

- Chart lines that were dark grey and invisible in dark mode now use teal.

## [0.1.0] - 2026-10-31

### Added

- `engtoolkit` Python package with a shared materials database, standard catalogs and a registry
  of validated tools for thermodynamics and fluids and for structural analysis.
- Web app (React, TypeScript, Tailwind) running the package in the browser via Pyodide, with forms
  and result cards generated from the tool registry, interactive charts, shareable URLs and
  Markdown/CSV downloads.
- Deployment to GitHub Pages, continuous integration, and MIT licence.

### Changed

- Notebooks moved into discipline folders and rewritten to use `engtoolkit`.
- Project rebranded as AA Engineering Toolkit.

[Unreleased]: https://github.com/areebahmed401/aa-engineering-toolkit/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/areebahmed401/aa-engineering-toolkit/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/areebahmed401/aa-engineering-toolkit/releases/tag/v0.1.0
