# MATSim-UAM modified source snapshot

For the exact executable, download the [prepared toolkit bundle](https://github.com/Chirag-Srinivas/UST-Toolkit/releases/tag/v1.0.2-prepared).
It already places the modified JAR in `lib/matsim-uam-5.0.0.jar`; no patching
or Java rebuild is needed. A source checkout omits the JAR. See the
[download and checksum guide](../../docs/RUNTIME-DOWNLOAD.md) for both workflows.

This folder accompanies `../matsim-uam-5.0.0.jar` and contains:

- `LICENSE`: the GPL-3.0 licence;
- `UPSTREAM_README.md`: the upstream project documentation;
- `pom.xml`: the Maven build declaration;
- `src/main/`: the modified local Java source and resources supplied alongside the executable.

The 1.0.2 runtime was built from this source in a clean Maven environment.
See [build validation](../../docs/JAVA-BUILD-VALIDATION.md), `MODIFICATIONS.md`
and `PROVENANCE.json` for the exact build hash and comparison limits.

The toolkit runs the JAR directly; users do not need to build this source for a
normal simulation. The executable main class is
`net.bhl.matsim.uam.run.RunUAMScenario`.

The UAM DTD used by the Java project is already present under
`src/main/resources/dtd/uam.dtd`. A separate machine-level or drive-level DTD
folder is not required by the UST pipeline.

MATSim-UAM 5.0.0 targets MATSim 2024.0 and Java 21. Refer to the Maven file and
upstream documentation for Java build details and dependency sources.
