# Changelog

## 1.0.2 - verified source build

- Supply a clean Java 21 build from the included source, removing two stale compiled classes.
- Compare all application code, bundled dependency classes and module declarations.
- Verify original/rebuilt runtimes in four synthetic no-PT simulations.
- Repair upstream comparison patch formatting and record build and content-review evidence.
- Preserve the original 1.0.0 and 1.0.1 release assets and separate MSc archive.

## 1.0.1 - optional public transport correction

- Support empty train/bus lists and disabled PT while retaining the UAM fleet.
- Emit a schema-required unused vehicle type with no PT vehicles or departures.
- Omit unavailable PT demand alternatives and reject explicit PT requests early.
- Validate transport settings in `pipeline.py --check`; add six regression tests.
- Verify both no-PT modes in two-iteration synthetic Java runs.
- Preserve the original 1.0.0 bundle, runtime JAR and separate MSc archive.

## 1.0.0 — prepared research release

- Separate a fresh, scenario-neutral toolkit from the frozen MSc evidence.
- Preserve IRP_RESULTS_FINAL, including T1, as the definitive study; retain
  IRP_RESULTS_NEW and IRP_results as labelled historical experiments.
- Include the modified MATSim-UAM Java source, comparison patch, upstream
  credits, GPL licence and current executable hash.
- Include the compiled local dashboard and explicit missing-trip-data notices.
- Supply independent analytical tests and a synthetic topology fixture.
- Record authorship and a maintenance policy with no promised future updates.

Original UST code is licensed under GPL-3.0-only, as confirmed by the owner.
Versions 1.0.0, 1.0.1 and 1.0.2 were prepared as private research prereleases.
See docs/RELEASE-READINESS.md for publication status and validation limits.
