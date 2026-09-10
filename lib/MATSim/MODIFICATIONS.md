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

The release executable has the SHA-256 recorded in `PROVENANCE.json`. It is
byte-identical to the current working executable and both previous toolkit ZIP
source folders. This audit has not rebuilt it or established which executable
revision was used for every historical run. Existing loose target/classes files
are not all byte-identical to the JAR and are not treated as authoritative.
The original source snapshot is preserved in the MSc archive.

## Confirmed runtime and comparison references

The owner confirmed MATSim 2024.0, Java 21 and UAM Extension 5.0.0.
The current edited POM declares these versions. The release keeps the working
JAR and POM; their hashes are recorded in `PROVENANCE.json`.

The owner also supplied a separate JAR/POM pair. Both differ from the working
files. Their hashes are recorded as comparison references, without assuming
they are unmodified upstream files. A detailed comparison of that pair is
deferred. The existing patch compares against the upstream tag only.

## Building from the supplied source

Install Java 21 and Maven, then run `mvn clean package` in this directory.
Dependencies are declared in `pom.xml`; access to those repositories is needed.
This is the declared build procedure, not a newly verified clean-build claim.
Before a public binary release, confirm corresponding-source build coverage,
including applicable notices/source obligations for bundled dependencies.
