# Java source and runtime validation

Completed 13 September 2026. The 1.0.2 prepared runtime is the output of a clean
build of the supplied Java source. The original working JAR remains preserved
in releases 1.0.0 and 1.0.1.

## Build identity

- Source commit: `360a098aad38094f81b35f5c731d3396f22d1eb4`.
- [Successful verification run](https://github.com/Chirag-Srinivas/UST-Toolkit/actions/runs/34772357127).
- Ubuntu x86-64; BellSoft Liberica JDK 21.0.12+10-LTS; Maven 3.9.16;
  Python 3.12.14 for the synthetic pipeline.
- MATSim 2024.0 and locally modified MATSim-UAM 5.0.0.
- Source copied into a separate build directory; Maven dependency repository
  initially empty. No existing `target/classes` used.
- Built 146 Java source files into 163 application class files.
- Original JAR: 89,310,293 bytes;
  SHA-256 `df139dc1ad847888ab55ffad74960ee022000b7b5afa51d7ae712443a463db4b`.
- Clean-built JAR: 89,251,954 bytes; SHA-256 `e0a4e3790b31a7d54bb0abbb52512bd7844184d8b4cc2a74e65e7ad642ea8118`.

The build command is equivalent to:

```bash
mvn -B -ntp -Dmaven.repo.local=/absolute/empty/m2 -f lib/MATSim/pom.xml clean package
```

The verification workflow retains toolchain output, Maven build log, dependency
tree, comparison reports and simulation logs. Durable compact evidence is
included in [evidence/](evidence/): `java-comparison.json`,
`module-descriptors.json`, `bundled-dependencies.json`,
`dependency-tree.txt`, `java-version.txt`, `maven-version.txt` and
`smoke-results.json`. The separate release package checks the exact tested
runtime hash and that Java source/POM are unchanged from the verification commit.

## Original versus rebuilt runtime

| Check | Result |
| --- | --- |
| Rebuilt application classes | 163 |
| Byte-identical application classes | 143 |
| Remaining common application classes | 20; identical normalized disassembly |
| Original-only classes | Two legacy scoring inner classes |
| Rebuilt-only application classes | None |
| Retained class references to the two legacy classes | None found |
| Dependency class entries | 35,897; no missing or added entries |
| Byte-identical dependency class entries | 35,894 |
| Remaining dependency entries | Three module descriptors; identical javap declarations |
| UAM DTD resources | Byte-identical |

The original-only classes are
`UAMScoringFunctionFactory$PostBoardingQueueScoring` and
`UAMScoringFunctionFactory$VertiportWaitingScoring`. They have no corresponding
definitions in the supplied source. No retained original class contains their
internal class names. The clean build omits them.

For byte-different application classes, `javap -c -p -s -constants` compares
instructions, branch targets, signatures and constants, normalizing constant
pool indices. The three dependency differences are
`META-INF/versions/{9,12,14}/module-info.class`; their declarations are checked
separately rather than treating their different bytes as executable-code changes.
See the recorded descriptor output for both JARs.

This establishes the stated code correspondence and direct source origin of
the clean runtime. It does not claim whole-JAR byte reproducibility or prove
that no reflective access is possible in arbitrary external code. ZIP timestamps
and build metadata vary between builds. The clean JAR is a new versioned
artifact, not a replacement for preserved historical hashes.

## Synthetic simulations

The deterministic fixture creates a six-node road network, two vertiports,
a bidirectional aerial route, four aircraft and 12 travellers. Each case runs
iterations 0 and 1, including all Python pipeline stages, the Java simulation
and analytics extraction.

| Runtime | Public transport | Iteration 0 | Iteration 1 |
| --- | --- | --- | --- |
| Original | Empty train/bus lists | 12 arrived; 8 UAM trips | 12 arrived; 4 UAM trips |
| Original | Explicitly disabled | 12 arrived; 8 UAM trips | 12 arrived; 4 UAM trips |
| Clean build | Empty train/bus lists | 12 arrived; 8 UAM trips | 12 arrived; 4 UAM trips |
| Clean build | Explicitly disabled | 12 arrived; 8 UAM trips | 12 arrived; 4 UAM trips |

All cases have zero stuck agents, matched UAM pickups/drop-offs, emitted
pre-boarding and post-boarding wait events, no PT plans, and zero unobserved
travellers. Final analytics record four completed UAM trips and eight car
travellers. Both original/rebuilt pairs have equal recorded iteration counts
and outcome summaries, including urgency-group outcomes.

The earlier verification fixture was corrected to include a required route ID.
A later strict byte-only dependency gate identified the three module descriptors;
the final workflow explicitly compares their declarations. The successful
run above is the release evidence.

## Limits

The tests cover these small synthetic no-PT cases. They do not validate every
dispatcher configuration, multi-person request, fleet design, charging scenario,
or historical MSc experiment. No claim of model calibration or scientific
convergence follows from two iterations. Historical Windows tests, configured
bus checks and dashboard checks retain their original scope in
[VALIDATION.md](VALIDATION.md). The clean-build checks here ran on Linux.
