# Fresh-install validation — 10 September 2026

**Historical 1.0.0 result:** the defect below is resolved in 1.0.1; see
[the correction and its validation](OPTIONAL-TRANSPORT-FIX.md). The original
release and its hashes remain unchanged.

**Result: qualified pass, with one release-blocking defect in the documented
UAM/car-only setup.** The unchanged supplied JAR completed a small synthetic
simulation with a configured bus service, and its analytics and dashboard
worked. The documented configuration with empty train and bus lists failed
before Java started. Do not describe this prerelease as fully validated.

## Artifact and environment

- Tested artifact: `UST-Toolkit-v1.0.0.zip`, 91,563,321 bytes, as attached to
  `v1.0.0-prepared`.
- ZIP SHA-256: `8aff19d9b70cc62c5829ff16753dd5ba0fac4353e69012fa5e0adb5ced3457d0`.
- Runtime SHA-256: `df139dc1ad847888ab55ffad74960ee022000b7b5afa51d7ae712443a463db4b`.
- Windows host; Python 3.12.14 in a newly created virtual environment without
  system site packages; BellSoft OpenJDK 21.0.11+11-LTS.
- Dependencies installed from the release's declared requirements. Pip used
  its download cache, but no packages were inherited from an existing venv.
  `pip check` passed. The exact installed versions accompany this report.
- This was a fresh extraction and Python environment on the existing Windows
  machine, not a new operating-system installation or container.
- No toolkit implementation or JAR was patched for the successful run. Only
  the intended user inputs (`src/config.py` and `data/base_network.xml`) were
  supplied. After execution, 494 other manifest-listed files remained
  byte-identical. The pipeline replaced its two output-folder placeholders as
  designed; the user configuration was the other changed manifest entry.

## Checks and observed results

| Check | Result |
| --- | --- |
| Fresh dependency installation and `pip check` | Pass |
| Python source compilation | Pass |
| All nine packaged unit tests | Pass |
| Blank configuration fails with actionable missing-input messages | Pass |
| Documented empty train/bus configuration | **Fail: Module 3 rejects it** |
| `pipeline.py --check` catches that transport failure | **Fail: reports success** |
| Full pipeline with one configured synthetic bus service | Pass, exit 0, 17.69 seconds |
| MATSim NetworkCleaner, topology, demand, supply and configuration generation | Pass in the configured-service run |
| MATSim iterations 0 and 1 using the supplied JAR | Pass |
| Module 5 extraction and readable Parquet outputs | Pass |
| Ten live HTTP checks | Pass |
| Browser navigation, charts, playback and iteration selection | Pass |

The supplemental fixture used six road nodes and 14 directed road links in a
synthetic projected network, two vertiports, four two-seat aircraft, and 12
passengers. Eight initially selected UAM and four selected car. One synthetic
bus corridor with four vehicles and 30-minute headways was supplied to get
past the empty-transport defect. Passenger PT alternatives were disabled; this
does not validate passenger PT route choice or interchange behaviour.

| Observed event result | Iteration 0 | Iteration 1 |
| --- | ---: | ---: |
| Passengers reaching their final destination | 12 / 12 | 12 / 12 |
| UAM pick-ups | 8 | 4 |
| UAM drop-offs | 8 | 4 |
| Stuck events | 0 | 0 |

The change in UAM use occurred across replanning iterations. The final
analytics reported four completed UAM journeys, eight car outcomes and zero
unobserved travellers, agreeing with the events. Both iterations emitted the
modified runtime's pre-boarding and post-boarding wait events. Score history
contained two rows with finite values; final executed score was
39.60023865583669.

The final analytics Parquet files were readable and nonempty: 196 trajectory
points, 12 traveller outcomes, 59 queue rows, 59 capacity rows and two FATO
headway rows. The Operations view reported no FATO separation or rolling
capacity violations for this small, lightly loaded fixture.

Live requests to `/`, `/api/health`, `/api/manifest`, `/api/iterations`,
`/api/matsim-results`, `/api/analytics`, and analytics for iterations 0 and 1
returned HTTP 200. Missing iteration 999 returned 404 and negative iteration
returned 422. The reported schema version was 8.

Browser checks covered all five views, play/pause with time advancing,
switching from iteration 1 to 0, passenger-outcome counts, score and mode-share
charts, queue/capacity displays, and selecting either vertiport. The dashboard
rendered the map and charts. No warning/error entries were returned by the
browser log inspection. Nearby labels overlapped at the initial map zoom;
that is a presentation limitation, not a failed simulation.

## Defect requiring correction

The release documentation and default configuration say that scheduled
transport is optional and train/bus lists may be left empty. With all other
synthetic inputs configured, this declaration:

```python
TRANSPORT_SUPPLY = {"enabled": True, "trains": [], "buses": []}
```

passes `python src/pipeline.py --check`, but the full pipeline exits with:

```text
module3_transport.TransportConfigError: At least two public-transport stops are required.
```

The observed path is `pipeline.main` -> `TransportSupplyGenerator.__init__`
-> `normalise_transport_config`, which requires at least two stops even when
no services were requested. Source inspection also shows that setting
`enabled=False` is not a supported full-pipeline workaround:
`TransportSupplyGenerator.generate` raises when disabled, while the pipeline
always invokes it and Module 4 requires its supply files.

Correction should make the no-public-transport path produce the necessary
empty transit supply and UAM fleet, or consistently configure the Java run
without scheduled transit. Preflight validation should also reject unsupported
transport configurations before declaring success. Add a full-pipeline
regression check for a two-vertiport UAM/car scenario, then repeat this
fresh-extraction test on a newly versioned bundle.

The configured-bus run demonstrates that the supplied runtime works; adding
fictional public transport to a real study is not a modelling workaround.

## Warnings and limits

MATSim logged deprecated configuration aliases, model-assumption warnings,
zero-length FATO resource links and automatic storage-capacity enlargement
for short, high-capacity internal links. These did not abort the smoke test,
but the traffic-dynamics warnings should be reviewed before quantitative
research use.

This test does not establish a clean source-to-binary rebuild, bit-identical
reproducibility, convergence, calibrated behaviour, large-network performance,
all PT modes, other operating systems, offline basemap availability or the
provenance of every historical simulation. No original MSc simulation or
archive was changed or rerun. The released ZIP and its checksums remain
unchanged; this report records findings against that exact artifact.

Machine-readable results and installed dependency versions are in
[`validation/2026-09-10/`](validation/2026-09-10/). Detailed logs, both synthetic
configuration snapshots, fixture generation and verification scripts are
retained in the local `.release-validation/2026-09-10-fresh-install` evidence
directory alongside the extracted test copy.
