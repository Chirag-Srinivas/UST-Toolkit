# Release preparation status

The toolkit's technical pre-publication checks are complete for the prepared
1.0.2 research release. The repository remains private. See the
[download guide](RUNTIME-DOWNLOAD.md), [Java build evidence](JAVA-BUILD-VALIDATION.md),
and [public-content review](PUBLIC-CONTENT-REVIEW.md).

## Completed

- Original UST code licensed GPL-3.0-only with the owner's approval; author
  Chirag Srinivas and research maintenance policy recorded.
- Java source compared with official MATSim-UAM v5.0.0: nine modified and nine
  added Java files, a modified POM, 139 unchanged files and no deletions.
- Corrected comparison patch applies and reconstructs all 19 changed files.
- Java 21/MATSim 2024.0 source built with an empty Maven dependency repository.
- Rebuilt application code compared with the original runtime; the two
  unreferenced legacy scoring classes are absent from the clean build.
- Original and clean runtimes complete both no-PT modes in synthetic
  two-iteration simulations, with matching recorded outcomes.
- Python regression checks and frontend CI pass.
- Release packaging verifies every file and runtime hash; history and release
  scans check credential patterns and excluded archive paths.
- Third-party notices, dependency inventory and upstream test-data provenance
  recorded. The approved UST licence does not replace third-party terms.

## Scope

Use 1.0.2 for the source-built runtime and repaired patch. Historical 1.0.0 and
1.0.1 assets retain their original hashes. No claim of byte-identical
reproducible JAR builds is made: ZIP/build metadata varies, and the original
JAR includes two stale classes.

The 34.56 GB MSc archive stays outside Git and toolkit releases. IRP_RESULTS_FINAL
including T1 remains the definitive preserved study; other roots are historical.
Publishing that archive or new study inputs requires a separate data-rights
review. The supplied upstream Corsica test fixtures are identified separately
in the public-content report.

These checks validate the documented synthetic cases. They do not rerun every
MSc experiment, establish the executable used by every historical run, prove
scientific convergence, or establish redistribution rights for user inputs.
The owner can choose when to make this prepared research repository public.
