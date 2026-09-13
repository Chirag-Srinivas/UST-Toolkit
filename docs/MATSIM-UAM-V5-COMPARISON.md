# MATSim-UAM v5.0.0 compared with the UST working source

Completed 11 September 2026.

The comparison identifies **18 changed Java files: nine modified and nine added**, plus a modified `pom.xml`. Across the complete source tree and POM, **139 files are unchanged and none are deleted**. Resource files, including the UAM DTD, have no content changes.

The working source and POM inspected on E: were **byte-identical to the prepared release source copy**. The comparison initially used `3f4a73ce18ef4b96de2fdaf2a702b314fdc8fae5`, the commit tagged `v1.0.1-prepared`.

## Baseline and method

- Official upstream: [BauhausLuftfahrt/MATSim-UAM v5.0.0](https://github.com/BauhausLuftfahrt/MATSim-UAM/tree/v5.0.0).
- Confirmed tag commit: [d11241567d56c262da8cdd5752828556f9080d68](https://github.com/BauhausLuftfahrt/MATSim-UAM/commit/d11241567d56c262da8cdd5752828556f9080d68). The GitHub tag API and the clean local upstream checkout agreed.
- Working project inspected: `E:\MATSim_Environment\MATSim-UAM\MATSim-UAM-master`.
- Prepared source inspected: `E:\MATSim_Environment\MatSim UST\src\UST-GitHub\lib\MATSim`.
- Compared every file under `src`, plus `pom.xml`; upstream comparisons normalize CRLF/LF line endings. Compared working versus prepared copies using raw bytes.
- Reviewed every changed Java file and the POM to explain behavior. Differences establish divergence from the tag, not authorship of each line.
- E: became unavailable when work resumed. The complete local comparison had already been captured. Final patch validation used the corresponding upstream and release files fetched from GitHub.

## Exact file changes

Java paths below are relative to `src/main/java/net/bhl/matsim/uam/`. Each link opens the released file.

| File | Status | Effect |
| --- | --- | --- |
| [pom.xml](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/pom.xml) | Modified | Changes packaging from Maven Assembly to Shade 3.5.2; merges service-provider metadata, sets the executable main class and excludes dependency signature files. Excludes com.springsource.JAI and gt-coverage from the MATSim dependency; adds jai-imageio-core 1.4.0 and the MATSim osm contribution. |
| [config/UAMConfigGroup.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/config/UAMConfigGroup.java) | Modified | Adds maxPoolingWaitTime, default 300 seconds, with a non-negative constraint and XML configuration getter/setter. |
| [dispatcher/UAMClosestRangedPreferPooledDispatcher.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/dispatcher/UAMClosestRangedPreferPooledDispatcher.java) | Modified | Groups pending requests with identical origin/destination links, fills an available aircraft by passenger count, and defers an incomplete batch until its oldest request reaches the pooling wait threshold. Overflow stays queued. |
| [qsim/UAMQSimModule.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/qsim/UAMQSimModule.java) | Modified | Passes maxPoolingWaitTime to the non-charging dispatcher. The charging dispatcher remains on its existing path. |
| [schedule/UAMSingleRideAppender.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/schedule/UAMSingleRideAppender.java) | Modified | Adds batch scheduling while retaining the single-request entry point. Checks nonempty batches, common origin/destination and capacity; puts all requests in pickup/drop-off tasks and prevents pickup before now or the latest passenger-ready time. |
| [run/RunUAMScenario.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/run/RunUAMScenario.java) | Modified | Removes unconditional insertion of default UAM/access/egress scoring modes and the unscored uam_interaction activity. The supplied configuration must provide these parameters; the UST configuration writer does so. |
| [run/UAMModule.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/run/UAMModule.java) | Modified | Registers the three waiting-time trackers as singleton event handlers alongside the custom scoring factory. |
| [scenario/RunCreateUAMRoutedScenario.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/scenario/RunCreateUAMRoutedScenario.java) | Modified | Separates the config loaded for constructing the scenario; reads and writes station charger count/speed and vehicle charge/energy-consumption fields. This changes the expected CSV columns. |
| [scenario/utils/ConfigAddUAMParameters.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/scenario/utils/ConfigAddUAMParameters.java) | Modified | Uses the routing and scoring configuration group names in place of planscalcroute and planCalcScore. |
| [scoring/UAMScoringFunctionFactory.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/scoring/UAMScoringFunctionFactory.java) | Modified | Extends the standard MATSim scorer with event-based waiting utility using each person's subpopulation parameters. Rejects missing UAM mode parameters. |
| [replanning/LoggedPlanStrategy.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/replanning/LoggedPlanStrategy.java) | Added | Wraps an existing strategy, records its name in the person's replanningStrategy attribute, then delegates selection and lifecycle calls. |
| [replanning/LoggedChangeExpBeta.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/replanning/LoggedChangeExpBeta.java) | Added | Provides the logging wrapper around MATSim's ExpBetaPlanChanger using the configured brainExpBeta. |
| [replanning/LoggedSelectRandom.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/replanning/LoggedSelectRandom.java) | Added | Provides the logging wrapper around MATSim's RandomPlanSelector. |
| [scoring/UAMPreBoardingWaitEvent.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/scoring/UAMPreBoardingWaitEvent.java) | Added | Defines the uam pre-boarding wait event, including person, vehicle and duration. |
| [scoring/UAMPreBoardingWaitTracker.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/scoring/UAMPreBoardingWaitTracker.java) | Added | Measures UAM-leg departure to entry into a UAM vehicle; emits a wait event and clears per-iteration state. |
| [scoring/UAMPostBoardingQueueEvent.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/scoring/UAMPostBoardingQueueEvent.java) | Added | Defines the uam post-boarding queue event, including person, vehicle and duration. |
| [scoring/UAMPostBoardingQueueTracker.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/scoring/UAMPostBoardingQueueTracker.java) | Added | Measures vehicle entry to entry onto a link whose ID starts with link_fato_takeoff_; emits one event per tracked passenger. |
| [scoring/UAMVertiportActivityWaitEvent.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/scoring/UAMVertiportActivityWaitEvent.java) | Added | Defines the uam vertiport activity wait event, including person, activity type and duration. |
| [scoring/UAMVertiportActivityWaitTracker.java](https://github.com/Chirag-Srinivas/UST-Toolkit/blob/v1.0.1-prepared/lib/MATSim/src/main/java/net/bhl/matsim/uam/scoring/UAMVertiportActivityWaitTracker.java) | Added | Measures six named processing/waiting activities between their start/end events and emits activity-wait events. |

## What the research changes mean

### Pooling and scheduling

Upstream already supported pooling. The modification adds deliberate batch formation and a configurable wait for an aircraft to fill. Requests must share the same origin and destination **link IDs**, rather than merely nearby coordinates. New batches enforce passenger capacity and keep overflow for later scheduling.

The 300-second setting is a pooling threshold, **not a guaranteed maximum total passenger wait**. A request can still wait longer when no suitable aircraft is available. The new parameter is passed only to the non-charging dispatcher. The existing charging dispatcher was not modified.

The inherited en-route pooling path still uses request counts in places, while the new initial-batch path uses passenger counts. Multi-person requests and heterogeneous fleet capacities deserve targeted tests before claiming general support beyond the tested single-person-request scenarios; this comparison did not establish a new runtime failure.

### Waiting-time events and scoring

The added event pairs separate:

1. UAM-leg departure to boarding.
2. Boarding to entry onto the takeoff link.
3. Time spent in named vertiport processing/waiting activities.

The activity tracker recognizes `vertiport_entry`, `vertiport_boarding`, `vertiport_arrival`, `vertiport_interaction`, `uam_interaction` and `uam_terminal_wait`.

The custom score added to MATSim's normal scorer is:

```text
additional score =
    terminal_activity_seconds * beta_wait
  + (preboarding_seconds + postboarding_seconds) * (beta_wait - beta_uam_travel)
```

Here the coefficients are per second. The second term reclassifies wait already included in UAM-leg time from travel utility to waiting utility. Terminal activities receive waiting utility directly. The UST writer disables normal activity scoring for these activities, which is part of the intended configuration. Different activity scoring settings need separate checking for double counting.

The post-boarding tracker depends on UST's `link_fato_takeoff_` naming convention. Its measured duration can include boarding and movement before takeoff, so it should not automatically be interpreted as pure congestion delay.

### Plan-selection logging

The three added classes record which selection strategy was assigned and delegate the actual choice to MATSim. Their presence alone does not enable logging. The inspected UST Java wiring and Python configuration contain no references selecting these wrapper classes; they must be explicitly configured or bound for a run to use them.

### Compatibility and build

**MATSim 2024.0, Java 21 and extension version 5.0.0 were already declared upstream.** They are not version upgrades introduced by these edits.

Charging fields were already required by the upstream UAM DTD; the scenario-writer edits supply those fields. They do not introduce a new charging model. Existing CSV inputs for the older helper need the additional columns.

The changed Maven packaging can alter the final JAR even where Java source is unchanged. Service-file merging is particularly relevant to packaged Java dependencies. A successful source comparison does not establish a reproducible build or bytecode equivalence.

## Comparison patch validation

The original release's `UST_CHANGES.patch` contains two missing end-of-file newline markers. One joins the POM's closing line to the next file header; another joins a removed closing brace to an added blank line. On the retrieved upstream files, the original patch fails `git apply --check` with a patch-header error.

A corrected patch is supplied as [UST_CHANGES.patch](../lib/MATSim/UST_CHANGES.patch). Its Java changes are the same; only patch formatting was repaired.

Validation completed:

- Corrected patch passes `git apply --check`.
- Applied successfully to the ten affected upstream files, adding the nine new Java files.
- All 19 resulting files match the released source after CRLF/LF normalization.
- Every result matches its recorded source SHA-256 after restoring the recorded line-ending form: CRLF for the POM and LF for Java.
- Git emits four whitespace warnings for existing indentation/trailing whitespace in the modified POM. They do not prevent application and were preserved to reproduce the source.

Evidence: [patch-validation.json](evidence/patch-validation.json), [provenance-verification.json](evidence/provenance-verification.json). The corrected patch is now committed as `lib/MATSim/UST_CHANGES.patch` and included in 1.0.2. Historical 1.0.1 assets retain the original malformed patch.

To check the corrected patch from a clean checkout of the upstream tag:

```powershell
git apply --check "C:\path\to\upstream-v5-to-current.patch"
```

## Follow-up build verification

The source comparison above was completed on 11 September. The clean build
and original/rebuilt runtime checks were subsequently completed on 13 September.
See [Java build validation](JAVA-BUILD-VALIDATION.md) for the exact toolchain,
runtime hashes, legacy-class differences and synthetic simulation results.
The source comparison does not establish which executable was used for each
historical simulation.
