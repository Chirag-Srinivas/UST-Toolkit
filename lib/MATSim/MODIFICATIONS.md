# Modified MATSim-UAM distributed with UST

This is a modified research version of MATSim-UAM, not an unmodified upstream
release. The upstream project and original authors retain their attribution.
Chirag Srinivas's UST research uses this local variant. The snapshot and this
notice were prepared on 10 September 2026; historical edit dates are not
reconstructed from memory.

The comparison baseline is upstream v5.0.0, commit
`d11241567d56c262da8cdd5752828556f9080d68`. This is a comparison baseline,
not proof that every difference from that tag was authored by Chirag.

The differences include configurable pooling waiting time and batched passenger
scheduling; pre-boarding, post-boarding and terminal-activity wait events and
scoring; plan-selection logging; controller/scoring wiring; and scenario/build
compatibility changes. See `UST_CHANGES.patch` for the actual differences and
`PROVENANCE.json` for the file list, source hashes and recorded local timestamps.

The original copyright and licence materials are retained. The modified
MATSim-UAM component remains under GPL-3.0; see `LICENSE`.

The 1.0.2 executable has the SHA-256 recorded in `PROVENANCE.json` and comes
from a clean build of the included source. All 163 application classes match
the original executable's code; the original also contained two unreferenced
legacy scoring classes. Whole-JAR byte identity is not claimed. See
[build evidence](../../docs/JAVA-BUILD-VALIDATION.md).
The exact executable used for every historical experiment remains unestablished.
The original working JAR and source snapshot remain preserved in earlier
releases and the separate MSc archive.

## Confirmed runtime and comparison references

The owner confirmed MATSim 2024.0, Java 21 and UAM Extension 5.0.0.
The current edited POM declares these versions. The 1.0.2 release keeps this
source/POM and uses the clean-built JAR; original and current hashes are recorded
in `PROVENANCE.json`.

The owner also supplied a separate JAR/POM pair. Both differ from the working
files. Their hashes are recorded as comparison references, without assuming
they are unmodified upstream files. A detailed comparison of that pair is
deferred. The existing patch compares against the upstream tag only.

## Building from the supplied source

Install Java 21 and Maven, then run `mvn clean package` in this directory.
Dependencies are declared in `pom.xml`; access to those repositories is needed.
This procedure passed using an empty Maven dependency repository on Linux.
The resolved dependency tree and embedded licence/notice inventory are recorded
under `docs/evidence/` at the repository root. Preserve dependency terms when
redistributing or modifying the runtime.

The patch formatting was repaired after 1.0.1. `UST_CHANGES.patch` now applies
against the official v5.0.0 baseline and reconstructs all 19 changed files.
See [source comparison](../../docs/MATSIM-UAM-V5-COMPARISON.md).
