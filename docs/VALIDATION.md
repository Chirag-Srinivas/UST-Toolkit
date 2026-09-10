# Local release validation

Validation performed on Windows with Python 3.12 and Node.js 24 in September
2026. No original research run was rerun or modified.

Passed:

- Python source compilation.
- Nine automated tests covering synthetic demand, event-derived analytics,
  shared FATO capacity, result-table parsing, archived-run paths and cache serving.
- TypeScript checks and the clean toolkit dashboard production build.
- In-process HTTP checks for the compiled UI, health endpoint, T1 cached
  iteration catalogue (2, 37, 50), and the 51-row score history.
- Blank fresh configuration fails early with instructions instead of starting
  a simulation.
- All 35,356 files in the MSc archive read back with matching SHA-256 hashes.

The archive has its own manifest and verification record. Frontend dependencies
are locked by pnpm-lock.yaml. The exact Python validation environment is listed
in requirements-tested-windows-py312.txt; the toolkit still declares supported
version ranges in its normal requirements files.

Not established by these checks:

- A complete new Java/MATSim simulation on a clean machine.
- A clean rebuild proving source-to-binary correspondence for the modified JAR.
- The exact current-JAR provenance for every historical experiment.
- Browser visual/interaction validation of this fresh toolkit build.
- Input-data redistribution rights. Original UST code is now licensed under GPL-3.0-only by the owner; this does not change third-party data terms.

The small synthetic examples in examples/README.md are working Python tests,
not a claim that an empty fresh configuration is a runnable full scenario.
