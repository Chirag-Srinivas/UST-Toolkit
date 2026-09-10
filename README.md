# UAM Scenario Toolkit (UST)

**Download the complete toolkit:** [UST-Toolkit-v1.0.0.zip and checksums](https://github.com/Chirag-Srinivas/UST-Toolkit/releases/tag/v1.0.0-prepared).
This prepared prerelease includes the exact modified MATSim-UAM runtime and
compiled dashboard. No manual Java edits or rebuild are needed. See
[download, checksum and setup instructions](docs/RUNTIME-DOWNLOAD.md).
Sign in with repository access while this repository is private. GitHub's
automatic source ZIP and Git clones do not include the runtime JAR.

**Validation status:** a fresh-install simulation and dashboard test passed
with configured public transport. The documented empty train/bus setup fails
in Module 3 and needs correction. See [test results and limits](docs/FRESH-INSTALL-VALIDATION.md).

UST is a modular toolkit for designing, running, and inspecting Urban Air
Mobility scenarios with MATSim-UAM. It builds vertiport micro-topology,
multimodal passenger demand, scheduled surface transport, MATSim configuration,
and a browser-based analytics dashboard from user-supplied scenario parameters.

Author: **Chirag Srinivas** ([Chirag-Srinivas on GitHub](https://github.com/Chirag-Srinivas)). This is a research release; continued development or support is not promised. See [maintenance status](MAINTENANCE.md).

This is a fresh, scenario-agnostic source distribution. It contains no previous
case-study inputs, experiment matrix, population, base network, results, or
one-off analysis scripts. A user supplies a MATSim base network and edits
`src/config.py` to design a new scenario.

## Contents

- [What is included](#what-is-included)
- [How a fresh download works](#how-a-fresh-download-works)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Configure a scenario](#configure-a-scenario)
- [Run the toolkit](#run-the-toolkit)
- [Local analytics server](#local-analytics-server)
- [Repository layout](#repository-layout)
- [Generated outputs](#generated-outputs)
- [Validation and development](#validation-and-development)
- [Troubleshooting](#troubleshooting)
- [Scope and limitations](#scope-and-limitations)
- [Distribution](#distribution)
- [Contributing](#contributing)
- [Citation](#citation)
- [Licences](#licences)

## What is included

The five toolkit modules are:

| Module | File | Responsibility |
| --- | --- | --- |
| 1 | `src/module1_topology.py` | Adds demand hubs, vertiports, stands, FATO resources, access links, and aerial routes to a MATSim network. |
| 2 | `src/module2_demand.py` | Generates reproducible multimodal passenger plans, urgency subpopulations, and initial choices. |
| 3 | `src/module3_transport.py` | Generates optional rail/bus supply and the physical UAM fleet. |
| 4 | `src/module4_config.py` | Writes the MATSim scoring, routing, replanning, transit, and UAM configuration. |
| 5 | `src/module5.py` | Extracts cached analytics and provides the API used by the dashboard. |

`src/module0_network_cleaning.py` is the preprocessing helper used before
Module 1; it is not counted as one of the five modules. The end-to-end
orchestrator is `src/pipeline.py`.

The local dashboard server is deliberately kept as a separate file at
`src/local_server.py`. Starting the server never starts a new MATSim simulation.

The source distribution also includes:

- the modified MATSim-UAM runtime source; the fresh toolkit release ZIP also includes `lib/matsim-uam-5.0.0.jar`;
- the MATSim-UAM GPL-3.0 licence and modified local Java source under `lib/MATSim/`;
- the Module 5 React source and compiled browser assets;
- Python dependency and GitHub Actions configuration;
- empty input, generated-scenario, and output directories with guidance files.

## How a fresh download works

The fresh toolkit release ZIP includes the runtime but intentionally has no configured scenario. The source checkout requires the release runtime or a source build. A new
user completes four inputs:

1. place their uncompressed MATSim network at `data/base_network.xml`;
2. set the network CRS in `src/config.py`;
3. define vertiports, aerial routes, demand, and fleet parameters in
   `src/config.py`;
4. optionally define scheduled public transport or a base population.

The toolkit then generates every scenario file downstream of those inputs. The
generic setup checklist and copy-ready parameter shapes are in
[`experiment_inputs/README.md`](experiment_inputs/README.md).

## Requirements

The research runtime uses **MATSim 2024.0**, **Java 21**, and a locally modified
**UAM Extension 5.0.0**. The release ZIP preserves the current edited executable
and POM; see [runtime provenance](lib/MATSim/PROVENANCE.json).

- Python 3.11 or newer;
- Java 21 available as `java` on `PATH`;
- enough memory and disk space for the selected MATSim network and iteration
  count; the supplied pipeline currently gives Java an 8 GB maximum heap;
- an uncompressed MATSim network XML containing a routable car component;
- optional: Node.js 20+ and pnpm 10+ only when rebuilding the dashboard.

The bundled JAR was built for Java 21. The compiled dashboard is included, so
Node.js is not needed to configure, simulate, extract, or view a normal run.

## Quick start

Extract the ZIP or clone the repository, then create a virtual environment from
the repository root.

Windows PowerShell:

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

macOS or Linux:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Next:

1. copy the network to `data/base_network.xml`;
2. edit `src/config.py` using the scenario-input guide;
3. validate the setup;
4. run the pipeline.

```powershell
python src/pipeline.py --check
python src/pipeline.py
```

`--check` verifies the top-level files and required scenario declarations
without modifying the network or running MATSim.

## Configure a scenario

`src/config.py` is the single user-editable parameter file. It starts with empty
`VERTIPORTS`, `AERIAL_ROUTES`, and `DEMAND_EVENTS` lists so no legacy case study
can be run accidentally.

### Paths and identity

- `SCENARIO_NAME`: a short name for the new scenario;
- `BASE_NETWORK_PATH`: defaults to `data/base_network.xml`;
- `MATSIM_JAR_PATH`: defaults to the bundled JAR;
- `BASE_POPULATION_PATH`: optional existing MATSim population to merge;
- `MODULE5_CRS`: the base network CRS, for example `EPSG:25832`;
- `DEMAND_RANDOM_SEED`: reproducible passenger generation seed.

Paths can be overridden without editing the file:

```powershell
$env:UST_BASE_NETWORK_PATH = "D:\networks\my_network.xml"
$env:UST_BASE_POPULATION_PATH = "D:\populations\background.xml"
$env:UST_NETWORK_CRS = "EPSG:25832"
```

On macOS or Linux, use `export` with the same variable names. The JAR path can
also be overridden with `UST_MATSIM_JAR_PATH`.

### Network and coordinates

All demand, vertiport, waypoint, station, and stop coordinates must use the
same projected CRS and units as the base network. Module 1 currently snaps
demand and vertiport coordinates to a strongly connected, car-enabled node
within 150 m. Candidate road links must permit `car`, have capacity at least
500 vehicles/hour, and free speed at least 8 m/s.

Use unique MATSim-safe IDs. Aerial route IDs may contain letters, numbers,
periods, underscores, and hyphens. Each demand event must reference configured
origin and destination vertiport IDs.

### Vertiports and aerial routes

Each entry in `VERTIPORTS` defines its network coordinate, local terminal
layout, physical stands, FATO resources, movement separation, and passenger
processing time. `AERIAL_ROUTES` connects airborne nodes directly or through
projected waypoints. Set `bidirectional=True` when both directions are needed.

The geometry factors in `VERTIPORT_DESIGN_RULES` and aircraft envelope in
`UAM_VEHICLE_TYPE` are research-model assumptions. Replace the generic aircraft
values with the intended design data and record the source of every assumption.

### Demand

Each `DEMAND_EVENTS` entry controls source population, UAM adoption, release
time, release-delay distribution, urgency mix, and initially selected plan.
Module 2 gives eligible passengers UAM and ground alternatives. It can also add
a scheduled-PT alternative when transport services are configured.

### Surface transport

Leave `TRANSPORT_SUPPLY["trains"]` and `["buses"]` empty when no scheduled
surface transport is needed. When services are provided, Module 3 creates both
directions, resolves network paths, derives running times, circulates the
physical fleet, and writes schedule and vehicle files. See
[`src/module3_transport/README.md`](src/module3_transport/README.md).

### MATSim and analytics

Module 4 parameters control scoring, plan memory, replanning weights, iteration
count, and output intervals. Module 5 extraction is enabled by default, while
automatic browser launch is disabled. The local server can be started after the
run whenever the results are needed.

## Run the toolkit

From the repository root:

```powershell
python src/pipeline.py
```

The pipeline:

1. validates required files and top-level configuration;
2. repairs the network XML header and runs MATSim `NetworkCleaner`;
3. adds the configured UAM topology;
4. creates passenger demand;
5. creates scheduled surface transport files and the UAM fleet;
6. writes MATSim `config.xml`;
7. runs the Java simulation;
8. extracts Module 5 analytics.

`AUTO_CLEAN_OUTPUTS=True` replaces the repository `outputs/` directory before
each simulation. Copy results that must be retained before starting another
run. Set it to `False` only when the intended MATSim output-directory behaviour
has been reviewed.

Individual module entry points are available from `src`:

```powershell
cd src
python -m module1_topology
python -m module2_demand
python -m module3_transport
python -m module4_config
python -m module5 extract --force
```

Most modules require the preceding stage's output. The complete pipeline is the
supported starting point for a new scenario.

Optional synthetic background road demand is generated separately:

```powershell
cd src
python background_traffic_generator.py --agents 5000
```

This generator is not invoked by the pipeline. Calibrate synthetic demand
against appropriate observations or an OD matrix before using it as evidence.

## Local analytics server

After a successful run, start the separate server from the repository root:

```powershell
python src/local_server.py
```

It serves the API and compiled dashboard at `http://127.0.0.1:8765` and opens a
browser by default. Useful options include:

```powershell
python src/local_server.py --no-browser
python src/local_server.py --host 127.0.0.1 --port 9000
python src/local_server.py --run-dir "D:\runs\scenario-a" --cache-only
python src/local_server.py --run-dir "D:\runs\scenario-a" --cache-only --extract-missing-iterations
```

An archived run directory supplied with `--run-dir` must contain `outputs/` and
`input_snapshots/`. Cache-only mode requires an existing
`outputs/module5_analytics/analytics_bundle.json` and never launches MATSim.

The default server binds only to the local machine. It has no authentication;
do not expose it to an untrusted network.

## Repository layout

```text
UST-Toolkit/
├── .github/workflows/ci.yml
├── data/                         # user adds base_network.xml
├── experiment_inputs/            # fresh-scenario setup guide only
├── lib/
│   ├── matsim-uam-5.0.0.jar
│   └── MATSim/                   # GPL licence and modified local source
├── outputs/                      # generated MATSim and analytics results
├── scenarios/
│   ├── configs/
│   ├── networks/
│   ├── populations/
│   └── transport/
├── src/
│   ├── config.py                 # user scenario parameters
│   ├── module0_network_cleaning.py
│   ├── module1_topology.py
│   ├── module2_demand.py
│   ├── module3_transport.py
│   ├── module4_config.py
│   ├── module5.py
│   ├── local_server.py
│   ├── pipeline.py
│   ├── uam_geometry.py
│   ├── xml_writer.py
│   └── module5/frontend/         # React source and compiled dashboard
├── .gitattributes
├── .gitignore
└── requirements.txt
```

## Generated outputs

The normal pipeline creates:

```text
scenarios/networks/
  base_network_prepped.xml
  base_network_cleaned.xml
  network_with_uam.xml
  network_transport.xml           # only for pseudo-network transport inputs
  vertiport_design_report.json
scenarios/populations/
  population.xml
scenarios/transport/
  transit_schedule.xml
  transit_vehicles.xml
  uam_fleet.xml
  resolved_transport_supply.yaml
scenarios/configs/
  config.xml
outputs/
  output_events.xml.gz
  output_network.xml.gz
  ITERS/
  module5_analytics/
    analytics_bundle.json
    manifest.json
    trajectory_points.parquet
    queue_series.parquet
    capacity_series.parquet
    traveller_outcomes.parquet
```

Generated scenario and output files are ignored by Git. The base network is
also ignored so users do not accidentally publish third-party network data.

## Validation and development

Check the fresh scenario inputs:

```powershell
python src/pipeline.py --check
```

Compile the distributable Python source:

```powershell
cd src
python -m compileall -q .
```

Rebuild the frontend when its source changes:

```powershell
cd src/module5/frontend
pnpm install --frozen-lockfile
pnpm run build
```

The GitHub Actions workflow installs Python dependencies, compiles the Python
source, and performs a clean frontend build. Full MATSim integration is not run
in CI because the user-supplied network is deliberately absent.

Runtime test directories from development are not included in this release.

## Troubleshooting

### Scenario setup is incomplete

Read every item printed by `python src/pipeline.py --check`. The source download
will report missing scenario declarations until the user provides the network,
two or more vertiports, an aerial route, demand, a positive fleet size, and the
network CRS.

### Java is missing or incompatible

Run `java -version`. Install Java 21 and confirm the `java` executable is on
`PATH`. The bundled MATSim-UAM 5.0.0 JAR targets Java 21.

### A coordinate cannot snap to the network

Confirm that it uses the network CRS, lies near a suitable car-enabled link,
and falls within the 150 m search radius. Also check the link's modes, capacity,
free speed, and strong connectivity.

### Module import error

Use `python src/pipeline.py` from the repository root, or change into `src`
before using `python -m module_name`. Confirm the virtual environment is active
and `requirements.txt` is installed.

### Dashboard frontend is missing

Run the pnpm install and build commands under `src/module5/frontend`, then
restart `src/local_server.py`.

### Port 8765 is occupied

Stop the existing process or use another port, for example
`python src/local_server.py --port 9000`.

### Memory or long runtime

Adjust `-Xmx8G` in `src/pipeline.py` for the machine and scenario size. Large
network and events XML files can require substantial memory, disk space, and
processing time even though Module 5 streams inputs and caches derived data.

## Scope and limitations

- UST is a research modelling toolkit, not an aviation certification, safety
  case, engineering design, or planning approval tool.
- Geometry and capacity checks implement documented simulation assumptions and
  do not replace regulatory assessment.
- The compact scheduled-transport input cannot reconstruct official stops or
  timetables from network links. Use audited GTFS, BODS, or rail timetable data
  when real-service fidelity is required.
- Generic vehicle parameters and synthetic background demand must be replaced
  or calibrated for the intended study.
- Users are responsible for validating input licences, coordinate systems,
  network quality, behavioural parameters, and result interpretation.

## Distribution

One repository supports two versioned downloads:

| Download | Intended use |
| --- | --- |
| `UST-Toolkit-v1.0.0.zip` | Configure a fresh scenario; includes the modified runtime and dashboard. |
| `UST-MSc-Research-Archive-v1.0.0.zip` | Explore the frozen MSc project, including definitive and clearly labelled historical results. |

The research archive preserves `IRP_RESULTS_FINAL` (including T1) as the
definitive study. See [study provenance](experiments/msc-study/README.md).
Large downloads are release assets or external archive links, not Git files.
The [prepared toolkit prerelease](https://github.com/Chirag-Srinivas/UST-Toolkit/releases/tag/v1.0.0-prepared)
provides the exact toolkit bundle and checksum. The MSc archive download is
not hosted here. Public-release review remains documented in
[release readiness](docs/RELEASE-READINESS.md).

## Contributing

1. Create a focused branch.
2. Keep private or licensed scenario inputs and generated results out of Git.
3. Run the Python compilation and frontend production build checks.
4. Document configuration, schema, or behavioural changes.
5. Open a pull request describing the motivation, validation, and compatibility
   implications.

Do not commit credentials, virtual environments, `node_modules`, local caches,
or unlicensed datasets.

## Citation

See `CITATION.cff`. Cite Chirag Srinivas, the exact UST release, the final
repository URL and relevant MATSim/MATSim-UAM publications. Use the frozen
archive identifier when discussing MSc results. No DOI has yet been assigned.

## Licences

Original UST Python and frontend code is licensed under the **GNU General
Public License version 3 (GPL-3.0-only)**. Copyright (C) 2026 Chirag Srinivas.
See [LICENSE](LICENSE) for the full terms and [COPYRIGHT.md](COPYRIGHT.md)
for scope and attribution.

The bundled MATSim-UAM JAR is GPL-3.0. Its licence and modified local Java source are
under `lib/MATSim/`. The rebuild/provenance limits are documented in `lib/MATSim/MODIFICATIONS.md`. MATSim, frontend packages, Python packages, and user-provided
datasets retain their own licences.

## Acknowledgements

UST builds on [MATSim](https://www.matsim.org/) and the surrounding open-source
Python and web ecosystems. Module 5 uses FastAPI, Apache Arrow, React, deck.gl,
MapLibre GL, and Apache ECharts.
