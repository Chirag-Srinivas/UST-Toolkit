"""User-editable scenario parameters for the UAM Scenario Toolkit.

This file is intentionally scenario-neutral. A new download will not run until
the user supplies a MATSim base network and replaces the empty scenario input
collections below. See ``experiment_inputs/README.md`` for the setup checklist
and ``README.md`` for the complete field reference.

Paths default to locations inside the repository and can be overridden with
environment variables, keeping the toolkit portable between machines.
"""

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Scenario identity, files, and reproducibility
# ---------------------------------------------------------------------------

SCENARIO_NAME = "my_uam_scenario"
BASE_NETWORK_PATH = os.environ.get(
    "UST_BASE_NETWORK_PATH",
    str(PROJECT_ROOT / "data" / "base_network.xml"),
)
MATSIM_JAR_PATH = os.environ.get(
    "UST_MATSIM_JAR_PATH",
    str(PROJECT_ROOT / "lib" / "matsim-uam-5.0.0.jar"),
)
BASE_POPULATION_PATH = os.environ.get("UST_BASE_POPULATION_PATH", "")
REBUILD_NETWORK = True
AUTO_CLEAN_OUTPUTS = True
DEMAND_RANDOM_SEED = 42

# The coordinate reference system used by BASE_NETWORK_PATH, such as
# ``EPSG:25832``. Module 5 converts it to WGS84 for mapping.
# This must be set explicitly for each new scenario.
MODULE5_CRS = os.environ.get("UST_NETWORK_CRS", "")


# ---------------------------------------------------------------------------
# Module 1: network and vertiport topology
# ---------------------------------------------------------------------------

VERTIPORT_DESIGN_RULES = {
    "fato_dimension_factor_d": 1.5,
    "safety_area_margin_factor_d": 0.25,
    "safety_area_margin_min_m": 3.0,
    "surface_tlof_dimension_factor_d": 0.83,
    "elevated_tlof_dimension_factor_d": 1.0,
    "stand_dimension_factor_d": 1.2,
    "stand_protection_margin_factor_d": 0.4,
    "ground_taxi_route_width_factor": 1.5,
    "air_taxi_route_width_factor": 2.0,
}

# Add at least two vertiports. Coordinates must use the same CRS and units as
# the base network. The README contains a copy-ready, generic example.
VERTIPORTS = []

# Connect configured vertiports with one or more aerial routes. Waypoints use
# the base network CRS. Set ``bidirectional`` to generate the reverse route.
AERIAL_ROUTES = []


# ---------------------------------------------------------------------------
# Module 2: passenger demand
# ---------------------------------------------------------------------------

# Add at least one demand event. Each event identifies an origin, a destination,
# the access and UAM vertiports, release time, cohort size, and UAM adoption.
DEMAND_EVENTS = []


# ---------------------------------------------------------------------------
# Module 3: scheduled public transport and the UAM fleet
# ---------------------------------------------------------------------------

# Scheduled trains and buses are optional. Leave the lists empty for a UAM/car
# scenario. When supplied, endpoint coordinates must match the network CRS.
TRANSPORT_SUPPLY = {
    "enabled": True,
    "trains": [],
    "buses": [],
}

UAM_FLEET_FILE = "uam_fleet.xml"

# Set this to a positive integer no greater than the total physical stands
# declared in VERTIPORTS.
FLEET_SIZE = 0

# These are generic starter assumptions, not certified aircraft performance
# data. Replace them with values appropriate to the aircraft being modelled.
UAM_VEHICLE_TYPE = {
    "id": "generic_evtol",
    "capacity": 4,
    "overall_length": 15.0,
    "overall_width": 15.0,
    "range": 100000.0,
    "cruise_speed": 55.5,
    "vertical_speed": 5.0,
    "boarding_time": 300.0,
    "deboarding_time": 120.0,
    "turnaround_time": 900.0,
    "maximum_charge": 100.0,
    "energy_consumption_vertical": 1.0,
    "energy_consumption_horizontal": 1.0,
}

UAM_ACCESS_EGRESS_MODES = ("walk",)
UAM_SEARCH_RADIUS = 15000.0
UAM_MAX_POOLING_WAIT_TIME = 300.0


# ---------------------------------------------------------------------------
# Module 4: MATSim scoring and replanning
# ---------------------------------------------------------------------------

BETAWAITHIGH = -24.0
BETAWAITLOW = -12.0
BETATRAVEL = -6.0
UTILITY_OF_LINE_SWITCH = -1.0

STRATEGIES_BY_SUBPOPULATION = {
    "high_urgency": {
        "ChangeExpBeta": 0.75,
        "SelectRandom": 0.25,
    },
    "low_urgency": {
        "ChangeExpBeta": 0.75,
        "SelectRandom": 0.25,
    },
    "default": {
        "ChangeExpBeta": 0.75,
        "SelectRandom": 0.25,
    },
}

MPLANS = 5
NITER = 50
INNOVATION_DISABLE_FRACTION = 0.80
WRITE_PLANS_INTERVAL = 10
WRITE_EXPERIENCED_PLANS = False


# ---------------------------------------------------------------------------
# Module 5: analytics and the separate local server
# ---------------------------------------------------------------------------

MODULE5_AUTO_EXTRACT = True
MODULE5_AUTO_LAUNCH = False
MODULE5_HOST = "127.0.0.1"
MODULE5_PORT = 8765
