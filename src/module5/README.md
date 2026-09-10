# UST Module 5 — Simulation analytics

Module 5 turns MATSim iteration events, network, population, standard result
tables, and the generated vertiport design into a connected analytics
application.

Python extraction, result-reading, API, and CLI code lives in `src/module5.py`.
The standalone local-server launcher is `src/local_server.py`. The
`module5/frontend` directory contains the web dashboard's source and compiled
static assets; those remain separate because they are delivered directly to
the browser.

## What is implemented

- timestamped main-car, muted background-car, and scheduled-public-transport
  playback, with the main travellers rendered at higher contrast;
- timestamped UAM vehicle playback across the configured aerial routes;
- an iteration selector that reloads the animation and analytical graphs from
  the selected `ITERS/it.N/N.events.xml.gz` file;
- a general MATSim results page for scores, mode share, passenger kilometres,
  mean travel/wait time by mode, travel distance, and runtime across the full
  iteration history;
- terminal-processing, UAM-dispatch, boarding-hold, and FATO occupancy series;
- passenger pickup waiting-time distribution;
- FATO rolling-throughput capacity checks per vertiport;
- per-FATO consecutive-movement separation checks against the configured
  `t_sep`, with take-offs and landings sharing one generated bottleneck link;
- UAM, scheduled-PT, car, and unobserved outcomes by urgency;
- generated stand, FATO, node, and internal-link plans for every configured
  vertiport;
- Parquet exports for trajectories, queues, capacity, and traveller outcomes;
- a cached browser bundle served by a local FastAPI application.

The frontend uses one shared visual language. deck.gl renders the regional
journey and vertiport plan; Apache ECharts renders all analytical plots.

## Install

From `src`:

```powershell
..\venv\Scripts\python.exe -m pip install -r module5\requirements.txt
cd module5\frontend
pnpm install
pnpm run build
```

The compiled frontend is written to `module5/frontend/dist` by the build
step. `node_modules` is not part of the toolkit.

## Run

From `src`:

```powershell
..\venv\Scripts\python.exe local_server.py
```

The application opens at `http://127.0.0.1:8765`. Alternatively, run
`module5\run_module5.ps1`, or use `python -m module5 serve` directly.

To reopen any archived run from its existing analytics cache without rerunning
MATSim, use:

```powershell
.\module5\run_module5.ps1 -RunDirectory "<run-folder>" -CacheOnly -ExtractMissingIterations
```

The run folder must contain `outputs/` and `input_snapshots/`. Cache-only mode
never launches MATSim. By itself it serves existing caches; adding
`-ExtractMissingIterations` permits parsing a selected uncached iteration once.
It reports a clear error
if `outputs/module5_analytics/analytics_bundle.json` has not already been built.
Without `-ExtractMissingIterations`, the iteration selector shows only the final
iteration plus earlier iterations that already have their own Module 5 cache.

Extract without starting the application:

```powershell
..\venv\Scripts\python.exe -m module5 extract --force
```

The normal toolkit pipeline now performs this extraction automatically after a
successful MATSim run. Set `MODULE5_AUTO_LAUNCH = True` in `config.py` if the
application should open immediately after every run.

## Generated data

The default analytics location is:

```text
outputs/module5_analytics/
  analytics_bundle.json
  manifest.json
  iterations/
    it.N/
      analytics_bundle.json
  trajectory_points.parquet
  queue_series.parquet
  capacity_series.parquet
  fato_headway_series.parquet  # written when comparable movement gaps exist
  traveller_outcomes.parquet
```

The manifest contains a source signature. Reopening Module 5 does not parse the
events and network again unless those inputs changed or `--force` is used.
Iteration bundles are built on first selection and then cached separately.
The journey animation derives walking trajectories from observed walk-leg
departure and arrival events, then finds a network-aligned route that strongly
prefers links permitting walking. Where isolated footpath components are not
connected, adjacent surface-road links bridge the display route. MATSim does not
emit intermediate link events for these teleported walk legs, so the observed
leg duration is distributed over that route without changing simulation results.

## Metric definitions

- **Background traffic in playback:** background traffic is enabled only when
  `BASE_POPULATION_PATH` in `config.py` is non-empty. People carrying the
  generated `backgroundTraffic=true` attribute are then marked on their
  trajectories and rendered as smaller slate-grey cars. Clearing the path
  disables those markers for every iteration and invalidates existing analytics
  caches. Main-agent cars remain larger and bright green.

- **Average travel time by mode:** arithmetic mean of `trav_time` for all
  trips assigned to each `main_mode` in every iteration's
  `ITERS/it.N/N.trips.csv.gz` table. Missing points mean that the mode had no
  trips in that iteration.
- **Average waiting time by mode:** arithmetic mean of the corresponding
  `wait_time` values. Waiting is a component of the observed trip time, not an
  additional duration to add to it.

- **Terminal processing:** passengers between `vertiport_entry` and
  `vertiport_boarding` activity starts. This is processing occupancy, not an
  unobserved physical queue.
- **UAM dispatch queue:** passengers between MATSim `passenger waiting` and
  `passenger picked up` events.
- **Picked-up awaiting departure:** picked-up passengers waiting for their
  assigned UAM vehicle to enter traffic. A pickup transfers a passenger from
  the dispatch queue into this stage; the passenger leaves this stage when the
  vehicle enters traffic.
- **FATO occupancy:** vehicles using the take-off or landing FATO link sequence.
  The Operations view displays this separately by vertiport because it counts
  aircraft, whereas the processing and dispatch chart counts passengers.
- **Capacity-breach proportion:** share of observed time where at least one
  vertiport's rolling one-hour FATO movement count exceeds its configured
  design capacity.
- **FATO headway violation:** a consecutive take-off/landing movement pair on
  the same physical FATO whose observed separation is shorter than that
  vertiport's configured `t_sep`. This is checked independently of the rolling
  one-hour capacity measure, so a short unsafe interval cannot be hidden by a
  low hourly movement total.

Capacity breaches and headway violations are retained as diagnostic validation
checks. Because the generated network enforces `t_sep`, they are not presented
as headline performance KPIs. The Operations page instead reports peak rolling
FATO utilisation and observed FATO movements; diagnostics become a warning only
if an enforced constraint is unexpectedly violated.

Module 1 routes arrivals and departures through one shared logical bottleneck
link for each physical FATO. Only that link receives the `t_sep`-derived flow
capacity. A conservative one-second QSim time-step guard is applied to the
enforcement link, while the reported design capacity continues to use the exact
configured `t_sep` value.
- **Observed journey outcome:** a completed UAM passenger drop-off takes
  precedence. Otherwise, executed departure events classify the journey as
  scheduled PT or car. A traveller with no recognised executed leg is shown as
  unobserved rather than being silently assigned to car.
- **UAM non-retention:** share of eligible travellers without an observed UAM
  passenger drop-off, including PT, car, and unobserved outcomes.

## Coordinate system

Set `MODULE5_CRS` in `config.py` to the coordinate reference system used by the
scenario network, or pass an explicit CRS when constructing
`AnalyticsExtractor`. Module 5 transforms projected network coordinates to
WGS84 for the regional map. A wrong CRS will misplace or suppress map geometry.
