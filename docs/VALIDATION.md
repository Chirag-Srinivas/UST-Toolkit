# Release validation

**13 September 2026:** a clean Java build and four original/rebuilt synthetic
simulations now pass. See [Java build validation](JAVA-BUILD-VALIDATION.md) and
[public-content review](PUBLIC-CONTENT-REVIEW.md). The 1.0.2 release uses the
clean-built runtime. The historical checks below retain their original scope.

**Current follow-up:** version 1.0.1 fixes the documented no-PT scenario.
Fifteen tests pass, and full Java runs pass for empty service lists and
explicitly disabled PT. See [fix validation](OPTIONAL-TRANSPORT-FIX.md).
The [original 1.0.0 report](FRESH-INSTALL-VALIDATION.md) records the earlier
configured-bus run, dashboard checks and defect.

The following records the earlier preparation checks and their original scope.

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

Not established by those earlier checks (the first two are now addressed by
the September 13 build report):

- A complete new Java/MATSim simulation on a clean machine.
- A clean rebuild proving source-to-binary correspondence for the modified JAR.
- The exact current-JAR provenance for every historical experiment.
- Browser visual/interaction validation of this fresh toolkit build.
- Input-data redistribution rights. Original UST code is now licensed under GPL-3.0-only by the owner; this does not change third-party data terms.

The small synthetic examples in examples/README.md are working Python tests,
not a claim that an empty fresh configuration is a runnable full scenario.
