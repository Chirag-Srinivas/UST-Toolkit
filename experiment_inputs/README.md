# Fresh scenario inputs

This folder contains guidance only. The source toolkit deliberately includes no
previous case-study files, experiment matrix, archived snapshots, population,
generated configuration, or results.

For a new scenario, the two authoritative user inputs are:

```text
data/base_network.xml             # the user's uncompressed MATSim network
src/config.py                     # the user's scenario parameters
```

The pipeline generates files under `scenarios/` and `outputs/`; do not place
generated results in this folder.

## Setup checklist

1. Confirm permission to use the chosen base network.
2. Copy it to `data/base_network.xml`, or set `UST_BASE_NETWORK_PATH`.
3. Identify its projected coordinate reference system and set `MODULE5_CRS`.
4. Choose at least two vertiport locations near suitable car-network nodes.
5. Replace the empty `VERTIPORTS`, `AERIAL_ROUTES`, and `DEMAND_EVENTS` lists in
   `src/config.py`.
6. Set a positive `FLEET_SIZE` that does not exceed total stand capacity.
7. Review the generic aircraft, geometry, scoring, and replanning assumptions.
8. Add optional rail/bus services or a base population only when required.
9. Run `python src/pipeline.py --check` from the repository root.
10. Resolve every reported item before running `python src/pipeline.py`.

## Generic parameter shapes

The following values are illustrative only. Replace every coordinate and all
operational assumptions with values appropriate to the new network and study.

```python
SCENARIO_NAME = "my_uam_scenario"
MODULE5_CRS = "EPSG:0000"  # replace with the base network's real EPSG code

VERTIPORTS = [
    {
        "id": "vp_a",
        "name": "Vertiport A",
        "x": 100000.0,
        "y": 200000.0,
        "layout": {
            "security": [20.0, 0.0],
            "gate": [40.0, 0.0],
            "stands": {
                "count": 2,
                "columns": 2,
                "origin": [70.0, 0.0],
                "orientation_deg": 180.0,
            },
            "apron": [120.0, 0.0],
            "fatos": [{"id": "F1", "center": [150.0, 0.0]}],
            "airborne": [170.0, 100.0],
        },
        "t_sep": 600,
        "t_process": 300,
    },
    {
        "id": "vp_b",
        "name": "Vertiport B",
        "x": 120000.0,
        "y": 210000.0,
        "layout": {
            "security": [20.0, 0.0],
            "gate": [40.0, 0.0],
            "stands": {
                "count": 2,
                "columns": 2,
                "origin": [70.0, 0.0],
                "orientation_deg": 0.0,
            },
            "apron": [120.0, 0.0],
            "fatos": [{"id": "F1", "center": [150.0, 0.0]}],
            "airborne": [170.0, 100.0],
        },
        "t_sep": 600,
        "t_process": 300,
    },
]

AERIAL_ROUTES = [
    {
        "id": "vp_a_to_vp_b",
        "from_vertiport": "vp_a",
        "to_vertiport": "vp_b",
        "bidirectional": True,
        "capacity": 120.0,
        "waypoints": [],
    }
]

DEMAND_EVENTS = [
    {
        "source_name": "Demand origin A",
        "origin_x": 99950.0,
        "origin_y": 200000.0,
        "vertiport_id": "vp_a",
        "dest_vertiport_id": "vp_b",
        "dest_x": 120050.0,
        "dest_y": 210000.0,
        "access_mode": "car",
        "flight_mode": "uam",
        "t_event": 28800,
        "c_source": 100,
        "uam_adoption": 0.10,
        "initial_uam_count": 5,
        "initial_ground_plan": "car",
        "release_delay_mean_s": 300,
        "release_delay_std_s": 30,
        "high_urgency_ratio": 0.50,
    }
]

FLEET_SIZE = 4
```

For a direct aerial line, `waypoints` may remain empty. Add waypoint dictionaries
such as `{"x": 110000.0, "y": 205000.0}` when the flight path must follow a
specified corridor.

## Optional scheduled transport

Leave the lists empty for a UAM/car scenario:

```python
TRANSPORT_SUPPLY = {
    "enabled": True,
    "trains": [],
    "buses": [],
}
```

A configured service uses endpoint locations in the base network CRS:

```python
TRANSPORT_SUPPLY = {
    "enabled": True,
    "trains": [
        {
            "start_location": {
                "name": "Station A",
                "x": 100000.0,
                "y": 200000.0,
            },
            "destination_location": {
                "name": "Station B",
                "x": 120000.0,
                "y": 210000.0,
            },
            "number_of_vehicles": 5,
            "frequency_minutes": 15,
        }
    ],
    "buses": [],
}
```

Module 3 derives network paths and operating times; it does not reconstruct an
official timetable from network XML. Use audited schedule data when real-world
service fidelity is required.

## Optional base population

Set `BASE_POPULATION_PATH` or `UST_BASE_POPULATION_PATH` only when an existing
MATSim population should be merged with the generated UAM-eligible passengers.
The population must be compatible with the same network and modes.

The separate `src/background_traffic_generator.py` can create synthetic car
demand, but it is not calibrated automatically and is never run by the normal
pipeline.

## Before interpreting results

Record the provenance of the network and every behavioural, operational,
vehicle, geometry, and timetable parameter. Check network connectivity, demand
scale, convergence, sensitivity, and MATSim warnings. UST output is a modelling
result, not an operational or regulatory approval.
