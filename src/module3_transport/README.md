# UST Module 3 — scheduled transport supply

The Python implementation is consolidated in `src/module3_transport.py`.
Module 3 uses the existing MATSim network for road and railway geometry, link
speeds, and link capacities. It generates only the supply data the network
cannot provide: transit stop facilities, a schedule, transit vehicles, the UAM
fleet, and a resolved audit manifest.

## Configuration

The normal scenario configuration in `config.py` stays compact:

```python
TRANSPORT_SUPPLY = {
    "trains": [
        {
            "start_location": {"name": "Station A", "x": 0.0, "y": 0.0},
            "destination_location": {"name": "Station B", "x": 1000.0, "y": 0.0},
            "number_of_vehicles": 5,
            "frequency_minutes": 15,
        }
    ],
    "buses": [],
}
```

`number_of_vehicles` is a reusable physical fleet. Module 3 automatically
creates departures in both directions from one hour before the earliest demand
event until four hours after the latest event. It then:

1. creates separate direction-correct platform facilities and outbound/return
   routes;
2. snaps locations to feasible links and finds least-travel-time paths;
3. adds internal mode-specific operating and recovery allowances to network
   free-flow time;
4. adds terminal layovers and assigns each departure only to a vehicle that is
   back at the correct terminal;
5. creates walking-transfer relations between nearby configured terminals;
6. rejects a fleet that cannot physically sustain the requested frequency;
7. writes and cross-validates the schedule, transit vehicles, audit manifest,
   and UAM fleet.

Passenger capacity, vehicle dimensions, and maximum vehicle speed are not
properties of a road or railway link. Module 3 uses central conservative
profiles (train: 300 seated + 200 standing; bus: 45 seated + 25 standing).

Exact intermediate stops and published timetable times cannot be recovered
from the current network XML because it contains links rather than a named
transit schedule. Those require an audited GTFS, BODS, or rail timetable data
source; Module 3 does not invent them. The full internal schema remains
accepted by `TransportSupplyGenerator(settings=...)` for specialised inputs.

## Run

From `src`:

```powershell
..\venv\Scripts\python.exe -m module3_transport
```

Outputs are written to `scenarios/transport/`:

```text
transit_schedule.xml
transit_vehicles.xml
uam_fleet.xml
resolved_transport_supply.yaml
```

The YAML manifest is generated output. It records actual snapped links, network
routes, operational allowances, physical fleets, vehicle assignments, and
files used by the run.
