"""Module 3 transport-supply generation for scheduled public transport and UAM."""

from __future__ import annotations

"""Validation and normalisation for declarative transport-supply settings."""


from copy import deepcopy
import math
import re


_TOKEN = re.compile(r"^[A-Za-z0-9_.-]+$")


class TransportConfigError(ValueError):
    """Raised when a transport-supply declaration is inconsistent."""


def checked_token(value: object, label: str) -> str:
    token = str(value)
    if not token or _TOKEN.fullmatch(token) is None:
        raise TransportConfigError(
            f"{label} {token!r} is not MATSim-safe; use letters, numbers, '.', '_' or '-'."
        )
    return token


def clock_seconds(value: object, label: str) -> float:
    if isinstance(value, (int, float)):
        result = float(value)
    else:
        parts = str(value).split(":")
        if len(parts) != 3:
            raise TransportConfigError(f"{label} must use HH:MM:SS, got {value!r}.")
        try:
            hours, minutes, seconds = (float(part) for part in parts)
        except ValueError as exc:
            raise TransportConfigError(f"{label} contains a non-numeric time: {value!r}.") from exc
        if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
            raise TransportConfigError(f"{label} is outside the valid clock range: {value!r}.")
        result = hours * 3600.0 + minutes * 60.0 + seconds
    if not math.isfinite(result) or result < 0:
        raise TransportConfigError(f"{label} must be a finite non-negative time.")
    return result


def matsim_time(seconds: float) -> str:
    total = int(round(float(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _positive(value: object, label: str, *, allow_zero: bool = False) -> float:
    number = float(value)
    valid = number >= 0 if allow_zero else number > 0
    if not math.isfinite(number) or not valid:
        qualifier = "non-negative" if allow_zero else "positive"
        raise TransportConfigError(f"{label} must be a finite {qualifier} number.")
    return number


_SIMPLE_MODE_DEFAULTS = {
    "rail": {
        "plural": "trains",
        "running_time_multiplier": 1.15,
        "running_time_allowance_s": 180.0,
        "layover_s": 600.0,
        "vehicle_type": {
            "id": "default_train",
            "mode": "rail",
            "seats": 300,
            "standing_room": 200,
            "length_m": 120.0,
            "width_m": 2.8,
            "maximum_velocity_m_s": 62.5,
            "passenger_car_equivalents": 5.0,
        },
    },
    "bus": {
        "plural": "buses",
        "running_time_multiplier": 1.30,
        "running_time_allowance_s": 120.0,
        "layover_s": 300.0,
        "vehicle_type": {
            "id": "default_bus",
            "mode": "bus",
            "seats": 45,
            "standing_room": 25,
            "length_m": 12.0,
            "width_m": 2.55,
            "maximum_velocity_m_s": 22.2,
            "passenger_car_equivalents": 2.5,
        },
    },
}


def _default_service_window() -> tuple[str, str]:
    """Cover the demand pulse without exposing timetable-window settings."""
    event_times = [
        float(event["t_event"])
        for event in getattr(config, "DEMAND_EVENTS", [])
        if isinstance(event, dict) and "t_event" in event
    ]
    if not event_times:
        return "00:00:00", "05:00:00"
    return (
        matsim_time(max(0.0, min(event_times) - 3600.0)),
        matsim_time(max(event_times) + 4.0 * 3600.0),
    )


def _simple_location(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise TransportConfigError(
            f"{label} must contain name, x, and y in the network coordinate system."
        )
    try:
        x, y = float(value["x"]), float(value["y"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TransportConfigError(f"{label} requires numeric x and y values.") from exc
    if not math.isfinite(x) or not math.isfinite(y):
        raise TransportConfigError(f"{label} coordinates must be finite.")
    return {"name": str(value.get("name", label)), "x": x, "y": y}


def _expand_simple_transport_config(raw: dict) -> dict:
    """Expand the compact config.py format into the validated internal schema.

    The public configuration describes only point-to-point trains and buses.
    Network links, running times, stop IDs, vehicle-type defaults, and output
    paths are implementation details resolved here.
    """
    simple_keys = {profile["plural"] for profile in _SIMPLE_MODE_DEFAULTS.values()}
    if not simple_keys.intersection(raw):
        return deepcopy(raw)
    if raw.get("services") or raw.get("stops") or raw.get("vehicle_types"):
        raise TransportConfigError(
            "Use either compact trains/buses declarations or the advanced services schema, not both."
        )

    default_start, default_end = _default_service_window()
    first_departure = str(raw.get("first_departure", default_start))
    last_departure = str(raw.get("last_departure", default_end))
    supply = {
        "enabled": bool(raw.get("enabled", True)),
        "input_mode": "locations",
        "output_directory": "transport",
        "transit_schedule_file": "transit_schedule.xml",
        "transit_vehicles_file": "transit_vehicles.xml",
        "uam_fleet_file": "uam_fleet.xml",
        "manifest_file": "resolved_transport_supply.yaml",
        "data_status": (
            "Routes resolve from the MATSim base network. Running times add "
            "mode-specific operating/recovery allowances; passenger capacities "
            "use conservative Module 3 vehicle profiles."
        ),
        "network": {
            "strategy": "network",
            "mode_map": {"rail": "pt", "bus": "car"},
            "route_cost": "travel_time",
            "stop_snap_radius_m": 1500.0,
            "stop_candidate_limit": 16,
            "snap_access_speed_m_s": 1.34,
        },
        "routing": {
            "algorithm": "SwissRailRaptor",
            "search_radius_m": 1500.0,
            "extension_radius_m": 200.0,
            "max_walk_connection_distance_m": 1000.0,
            "additional_transfer_time_s": 0.0,
        },
        "validation": {"minimum_running_time_tolerance_s": 1.0},
        "stops": [],
        "transfers": [],
        "vehicle_types": [],
        "services": [],
        "circulation_fleets": [],
    }

    for mode, profile in _SIMPLE_MODE_DEFAULTS.items():
        declarations = raw.get(profile["plural"], [])
        if not isinstance(declarations, list):
            raise TransportConfigError(f"TRANSPORT_SUPPLY[{profile['plural']!r}] must be a list.")
        if declarations:
            supply["vehicle_types"].append(deepcopy(profile["vehicle_type"]))
        for index, declaration in enumerate(declarations, start=1):
            if not isinstance(declaration, dict):
                raise TransportConfigError(
                    f"{profile['plural']}[{index - 1}] must be a mapping."
                )
            service_id = f"{mode}_{index}"
            start = _simple_location(
                declaration.get("start_location"), f"{service_id}.start_location"
            )
            destination = _simple_location(
                declaration.get("destination_location"),
                f"{service_id}.destination_location",
            )
            vehicle_count_value = _positive(
                declaration.get("number_of_vehicles"),
                f"{service_id}.number_of_vehicles",
            )
            if not vehicle_count_value.is_integer():
                raise TransportConfigError(
                    f"{service_id}.number_of_vehicles must be a whole number."
                )
            vehicle_count = int(vehicle_count_value)
            frequency_minutes = _positive(
                declaration.get("frequency_minutes"),
                f"{service_id}.frequency_minutes",
            )
            headway_s = frequency_minutes * 60.0
            start_seconds = clock_seconds(first_departure, "first_departure")
            end_seconds = clock_seconds(last_departure, "last_departure")
            if end_seconds < start_seconds:
                raise TransportConfigError("last_departure must not precede first_departure.")
            outbound_start_id = f"{service_id}_start_outbound"
            outbound_destination_id = f"{service_id}_destination_outbound"
            inbound_destination_id = f"{service_id}_destination_inbound"
            inbound_start_id = f"{service_id}_start_inbound"
            supply["stops"].extend(
                (
                    {
                        "id": outbound_start_id,
                        **start,
                        "_corridor": service_id,
                        "_terminal": "start",
                    },
                    {
                        "id": outbound_destination_id,
                        **destination,
                        "_corridor": service_id,
                        "_terminal": "destination",
                    },
                    {
                        "id": inbound_destination_id,
                        **destination,
                        "_corridor": service_id,
                        "_terminal": "destination",
                    },
                    {
                        "id": inbound_start_id,
                        **start,
                        "_corridor": service_id,
                        "_terminal": "start",
                    },
                )
            )
            common = {
                "mode": mode,
                "vehicle_type": profile["vehicle_type"]["id"],
                # The real value is filled from the resolved network path.
                "segment_travel_times_s": [1.0],
                "dwell_times_s": [0.0, 0.0],
                "service_start": matsim_time(start_seconds),
                "service_end": matsim_time(end_seconds),
                "headway_s": headway_s,
                "circulation_id": service_id,
                "layover_s": profile["layover_s"],
                "_derive_travel_times": True,
                "_running_time_multiplier": profile["running_time_multiplier"],
                "_running_time_allowance_s": profile["running_time_allowance_s"],
            }
            supply["services"].extend(
                (
                    {
                        **deepcopy(common),
                        "id": f"{service_id}_outbound",
                        "name": f"{start['name']} to {destination['name']}",
                        "stops": [outbound_start_id, outbound_destination_id],
                        "origin_terminal": "start",
                        "destination_terminal": "destination",
                    },
                    {
                        **deepcopy(common),
                        "id": f"{service_id}_inbound",
                        "name": f"{destination['name']} to {start['name']}",
                        "stops": [inbound_destination_id, inbound_start_id],
                        "origin_terminal": "destination",
                        "destination_terminal": "start",
                    },
                )
            )
            supply["circulation_fleets"].append(
                {
                    "id": service_id,
                    "mode": mode,
                    "vehicle_type": profile["vehicle_type"]["id"],
                    "vehicle_count": vehicle_count,
                    "service_ids": [
                        f"{service_id}_outbound",
                        f"{service_id}_inbound",
                    ],
                }
            )

    # Directional platform facilities at the same place, and nearby
    # interchanges between configured services, receive automatic walking links.
    for from_stop in supply["stops"]:
        for to_stop in supply["stops"]:
            if from_stop["id"] == to_stop["id"]:
                continue
            separation = math.hypot(
                to_stop["x"] - from_stop["x"],
                to_stop["y"] - from_stop["y"],
            )
            same_corridor = from_stop["_corridor"] == to_stop["_corridor"]
            if separation <= 1.0 or (not same_corridor and separation <= 1000.0):
                supply["transfers"].append(
                    {
                        "from_stop": from_stop["id"],
                        "to_stop": to_stop["id"],
                        "transfer_time_s": max(60.0, math.ceil(separation / 1.34)),
                    }
                )
    return supply


def normalise_transport_config(raw: dict) -> dict:
    """Return a validated copy of the configured transport supply."""
    if not isinstance(raw, dict):
        raise TransportConfigError("TRANSPORT_SUPPLY must be a mapping.")
    supply = _expand_simple_transport_config(raw)
    if not bool(supply.get("enabled", True)):
        supply["enabled"] = False
        return supply
    if supply.get("input_mode", "configured") not in {"configured", "locations"}:
        raise TransportConfigError(
            "input_mode must be 'configured' or the compact 'locations' format."
        )

    network = supply.setdefault("network", {})
    strategy = str(network.get("strategy", "network"))
    if strategy not in {"network", "pseudo_network"}:
        raise TransportConfigError(
            "network.strategy must be either 'network' or 'pseudo_network'."
        )
    network["strategy"] = strategy
    mode_map = network.setdefault("mode_map", {"rail": "pt", "bus": "car"})
    if not isinstance(mode_map, dict) or not mode_map:
        raise TransportConfigError("network.mode_map must map service modes to network modes.")
    network["mode_map"] = {
        checked_token(mode, "network.mode_map mode"): checked_token(
            network_mode, f"network.mode_map[{mode!r}]"
        )
        for mode, network_mode in mode_map.items()
    }
    network["route_cost"] = str(network.get("route_cost", "travel_time"))
    if network["route_cost"] not in {"travel_time", "distance"}:
        raise TransportConfigError(
            "network.route_cost must be 'travel_time' or 'distance'."
        )
    network["stop_snap_radius_m"] = _positive(
        network.get("stop_snap_radius_m", 1500.0), "network.stop_snap_radius_m"
    )
    network["stop_candidate_limit"] = int(
        _positive(
            network.get("stop_candidate_limit", 16),
            "network.stop_candidate_limit",
        )
    )
    network["snap_access_speed_m_s"] = _positive(
        network.get("snap_access_speed_m_s", 1.34),
        "network.snap_access_speed_m_s",
    )
    excluded = network.setdefault(
        "exclude_link_prefixes",
        [
            "link_origin_",
            "link_dest_",
            "link_base_to_vt_",
            "link_vt_to_base_",
            "link_passenger_",
            "link_security_",
            "link_gate_",
            "link_stand_",
            "link_apron_",
            "link_fato_",
            "link_airroute_",
        ],
    )
    network["exclude_link_prefixes"] = tuple(str(prefix) for prefix in excluded)
    network["stop_link_length_m"] = _positive(
        network.get("stop_link_length_m", 1.0), "network.stop_link_length_m"
    )
    network["stop_link_freespeed_m_s"] = _positive(
        network.get("stop_link_freespeed_m_s", 100.0),
        "network.stop_link_freespeed_m_s",
    )
    network["connector_speed_margin"] = _positive(
        network.get("connector_speed_margin", 1.05),
        "network.connector_speed_margin",
    )
    network["capacity_veh_h"] = _positive(
        network.get("capacity_veh_h", 9999.0), "network.capacity_veh_h"
    )

    validation = supply.setdefault("validation", {})
    validation["minimum_running_time_tolerance_s"] = _positive(
        validation.get("minimum_running_time_tolerance_s", 1.0),
        "validation.minimum_running_time_tolerance_s",
        allow_zero=True,
    )

    stops_by_id: dict[str, dict] = {}
    for index, stop in enumerate(supply.get("stops", [])):
        if not isinstance(stop, dict):
            raise TransportConfigError(f"stops[{index}] must be a mapping.")
        stop["id"] = checked_token(stop.get("id", ""), f"stops[{index}].id")
        if stop["id"] in stops_by_id:
            raise TransportConfigError(f"Duplicate transport stop id: {stop['id']}")
        stop["name"] = str(stop.get("name", stop["id"]))
        stop["x"] = float(stop["x"])
        stop["y"] = float(stop["y"])
        if not math.isfinite(stop["x"]) or not math.isfinite(stop["y"]):
            raise TransportConfigError(f"Stop {stop['id']} has non-finite coordinates.")
        stops_by_id[stop["id"]] = stop
    if len(stops_by_id) < 2:
        raise TransportConfigError("At least two public-transport stops are required.")

    vehicle_types_by_id: dict[str, dict] = {}
    for index, vehicle_type in enumerate(supply.get("vehicle_types", [])):
        if not isinstance(vehicle_type, dict):
            raise TransportConfigError(f"vehicle_types[{index}] must be a mapping.")
        vehicle_type["id"] = checked_token(
            vehicle_type.get("id", ""), f"vehicle_types[{index}].id"
        )
        if vehicle_type["id"] in vehicle_types_by_id:
            raise TransportConfigError(f"Duplicate transit vehicle type: {vehicle_type['id']}")
        vehicle_type["mode"] = checked_token(
            vehicle_type.get("mode", ""), f"vehicle type {vehicle_type['id']} mode"
        )
        vehicle_type["seats"] = int(
            _positive(vehicle_type.get("seats", 0), f"{vehicle_type['id']}.seats", allow_zero=True)
        )
        vehicle_type["standing_room"] = int(
            _positive(
                vehicle_type.get("standing_room", 0),
                f"{vehicle_type['id']}.standing_room",
                allow_zero=True,
            )
        )
        if vehicle_type["seats"] + vehicle_type["standing_room"] <= 0:
            raise TransportConfigError(f"Vehicle type {vehicle_type['id']} has zero capacity.")
        for key, default in (
            ("length_m", 12.0),
            ("width_m", 2.5),
            ("maximum_velocity_m_s", 20.0),
            ("passenger_car_equivalents", 1.0),
        ):
            vehicle_type[key] = _positive(
                vehicle_type.get(key, default), f"{vehicle_type['id']}.{key}"
            )
        vehicle_types_by_id[vehicle_type["id"]] = vehicle_type
    if not vehicle_types_by_id:
        raise TransportConfigError("At least one public-transport vehicle type is required.")

    services_by_id: dict[str, dict] = {}
    for index, service in enumerate(supply.get("services", [])):
        if not isinstance(service, dict):
            raise TransportConfigError(f"services[{index}] must be a mapping.")
        service["id"] = checked_token(service.get("id", ""), f"services[{index}].id")
        if service["id"] in services_by_id:
            raise TransportConfigError(f"Duplicate public-transport service: {service['id']}")
        service["name"] = str(service.get("name", service["id"]))
        service["mode"] = checked_token(service.get("mode", ""), f"{service['id']}.mode")
        if service["mode"] not in network["mode_map"]:
            raise TransportConfigError(
                f"Service {service['id']} mode {service['mode']!r} has no "
                "network.mode_map entry."
            )
        service["network_mode"] = network["mode_map"][service["mode"]]
        service["vehicle_type"] = checked_token(
            service.get("vehicle_type", ""), f"{service['id']}.vehicle_type"
        )
        if service["vehicle_type"] not in vehicle_types_by_id:
            raise TransportConfigError(
                f"Service {service['id']} references unknown vehicle type "
                f"{service['vehicle_type']!r}."
            )
        if vehicle_types_by_id[service["vehicle_type"]]["mode"] != service["mode"]:
            raise TransportConfigError(
                f"Service {service['id']} mode does not match vehicle type "
                f"{service['vehicle_type']}."
            )
        service["stops"] = [
            checked_token(stop_id, f"{service['id']}.stops")
            for stop_id in service.get("stops", [])
        ]
        if len(service["stops"]) < 2:
            raise TransportConfigError(f"Service {service['id']} requires at least two stops.")
        unknown_stops = [stop for stop in service["stops"] if stop not in stops_by_id]
        if unknown_stops:
            raise TransportConfigError(
                f"Service {service['id']} references unknown stops: {', '.join(unknown_stops)}"
            )
        if len(set(service["stops"])) != len(service["stops"]):
            raise TransportConfigError(
                f"Service {service['id']} repeats a stop; define loop services as separate routes."
            )
        service["segment_travel_times_s"] = [
            _positive(value, f"{service['id']}.segment_travel_times_s")
            for value in service.get("segment_travel_times_s", [])
        ]
        if len(service["segment_travel_times_s"]) != len(service["stops"]) - 1:
            raise TransportConfigError(
                f"Service {service['id']} needs one segment travel time between each stop."
            )
        dwell = service.get("dwell_times_s", [0.0] * len(service["stops"]))
        service["dwell_times_s"] = [
            _positive(value, f"{service['id']}.dwell_times_s", allow_zero=True)
            for value in dwell
        ]
        if len(service["dwell_times_s"]) != len(service["stops"]):
            raise TransportConfigError(
                f"Service {service['id']} needs one dwell time for every stop."
            )
        service["service_start_s"] = clock_seconds(
            service.get("service_start", "00:00:00"), f"{service['id']}.service_start"
        )
        service["service_end_s"] = clock_seconds(
            service.get("service_end", "30:00:00"), f"{service['id']}.service_end"
        )
        service["headway_s"] = _positive(service.get("headway_s"), f"{service['id']}.headway_s")
        if service["service_end_s"] < service["service_start_s"]:
            raise TransportConfigError(f"Service {service['id']} ends before it starts.")
        if service.get("circulation_id"):
            service["circulation_id"] = checked_token(
                service["circulation_id"], f"{service['id']}.circulation_id"
            )
            service["origin_terminal"] = checked_token(
                service.get("origin_terminal", ""),
                f"{service['id']}.origin_terminal",
            )
            service["destination_terminal"] = checked_token(
                service.get("destination_terminal", ""),
                f"{service['id']}.destination_terminal",
            )
            if service["origin_terminal"] == service["destination_terminal"]:
                raise TransportConfigError(
                    f"Service {service['id']} circulation terminals must differ."
                )
            service["layover_s"] = _positive(
                service.get("layover_s", 0.0),
                f"{service['id']}.layover_s",
                allow_zero=True,
            )
        services_by_id[service["id"]] = service
    if not services_by_id:
        raise TransportConfigError("At least one scheduled public-transport service is required.")

    for index, fleet in enumerate(supply.get("circulation_fleets", [])):
        if not isinstance(fleet, dict):
            raise TransportConfigError(f"circulation_fleets[{index}] must be a mapping.")
        fleet["id"] = checked_token(fleet.get("id", ""), f"circulation_fleets[{index}].id")
        fleet["mode"] = checked_token(
            fleet.get("mode", ""), f"circulation fleet {fleet['id']} mode"
        )
        fleet["vehicle_type"] = checked_token(
            fleet.get("vehicle_type", ""),
            f"circulation fleet {fleet['id']} vehicle_type",
        )
        count = _positive(
            fleet.get("vehicle_count"),
            f"circulation fleet {fleet['id']} vehicle_count",
        )
        if not count.is_integer():
            raise TransportConfigError(
                f"Circulation fleet {fleet['id']} vehicle_count must be a whole number."
            )
        fleet["vehicle_count"] = int(count)
        fleet["service_ids"] = [
            checked_token(service_id, f"circulation fleet {fleet['id']} service_ids")
            for service_id in fleet.get("service_ids", [])
        ]
        if any(service_id not in services_by_id for service_id in fleet["service_ids"]):
            raise TransportConfigError(
                f"Circulation fleet {fleet['id']} references an unknown service."
            )

    for index, transfer in enumerate(supply.get("transfers", [])):
        if not isinstance(transfer, dict):
            raise TransportConfigError(f"transfers[{index}] must be a mapping.")
        transfer["from_stop"] = checked_token(
            transfer.get("from_stop", ""), f"transfers[{index}].from_stop"
        )
        transfer["to_stop"] = checked_token(
            transfer.get("to_stop", ""), f"transfers[{index}].to_stop"
        )
        if transfer["from_stop"] not in stops_by_id or transfer["to_stop"] not in stops_by_id:
            raise TransportConfigError(f"transfers[{index}] references an unknown stop.")
        transfer["transfer_time_s"] = _positive(
            transfer.get("transfer_time_s"), f"transfers[{index}].transfer_time_s"
        )

    supply["stops_by_id"] = stops_by_id
    supply["vehicle_types_by_id"] = vehicle_types_by_id
    supply["services_by_id"] = services_by_id
    return supply



"""Build and inject a deterministic transit pseudo-network."""


import math
import os
from pathlib import Path
import heapq
import itertools
import tempfile
import xml.etree.ElementTree as ET

import networkx as nx



def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _point_segment_distance(px, py, ax, ay, bx, by) -> float:
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    fraction = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    fraction = max(0.0, min(1.0, fraction))
    return math.hypot(px - (ax + fraction * dx), py - (ay + fraction * dy))


def _read_modal_network(network_file: Path, supply: dict) -> tuple[dict, dict]:
    """Stream the finished network into separate mode graphs and link records."""
    network_file = Path(network_file)
    if not network_file.is_file():
        raise FileNotFoundError(f"MATSim network not found: {network_file}")
    required_modes = {service["network_mode"] for service in supply["services"]}
    graphs = {mode: nx.DiGraph() for mode in required_modes}
    records = {mode: [] for mode in required_modes}
    node_coordinates: dict[str, tuple[float, float]] = {}
    excluded_prefixes = supply["network"]["exclude_link_prefixes"]
    route_cost = supply["network"]["route_cost"]

    for _, element in ET.iterparse(network_file, events=("end",)):
        name = _local_name(element.tag)
        if name == "node":
            node_coordinates[element.get("id")] = (
                float(element.get("x")),
                float(element.get("y")),
            )
        elif name == "link":
            link_id = element.get("id")
            if link_id.startswith(excluded_prefixes):
                element.clear()
                continue
            modes = {
                mode.strip()
                for mode in element.get("modes", "car").split(",")
                if mode.strip()
            }
            matched_modes = modes & required_modes
            if matched_modes:
                from_node = element.get("from")
                to_node = element.get("to")
                if from_node not in node_coordinates or to_node not in node_coordinates:
                    raise TransportConfigError(
                        f"Network link {link_id} references a node without coordinates."
                    )
                length = float(element.get("length", "0"))
                freespeed = float(element.get("freespeed", "0"))
                if length <= 0 or freespeed <= 0:
                    element.clear()
                    continue
                weight = length if route_cost == "distance" else length / freespeed
                record = {
                    "id": link_id,
                    "from": from_node,
                    "to": to_node,
                    "length": length,
                    "freespeed": freespeed,
                    "from_xy": node_coordinates[from_node],
                    "to_xy": node_coordinates[to_node],
                    "weight": weight,
                }
                for mode in matched_modes:
                    records[mode].append(record)
                    previous = graphs[mode].get_edge_data(from_node, to_node)
                    if previous is None or weight < previous["weight"]:
                        graphs[mode].add_edge(
                            from_node,
                            to_node,
                            weight=weight,
                            link_id=link_id,
                            length=length,
                            freespeed=freespeed,
                        )
        element.clear()
    return graphs, records


def _stop_candidates(stop: dict, links: list[dict], radius: float) -> list[dict]:
    candidates = []
    for link in links:
        distance = _point_segment_distance(
            stop["x"],
            stop["y"],
            link["from_xy"][0],
            link["from_xy"][1],
            link["to_xy"][0],
            link["to_xy"][1],
        )
        if distance <= radius:
            candidates.append({**link, "snap_distance_m": distance})
    candidates.sort(key=lambda item: (item["snap_distance_m"], item["id"]))
    return candidates


def _links_for_node_path(graph: nx.DiGraph, nodes: list[str]) -> list[str]:
    return [graph[from_node][to_node]["link_id"] for from_node, to_node in zip(nodes, nodes[1:])]


def _reverse_reachable_nodes(graph: nx.DiGraph, targets: set[str]) -> set[str]:
    """Return nodes that can reach any target without materialising path lists."""
    reachable = set(targets)
    frontier = list(targets)
    while frontier:
        node = frontier.pop()
        if node not in graph:
            continue
        for predecessor in graph.predecessors(node):
            if predecessor not in reachable:
                reachable.add(predecessor)
                frontier.append(predecessor)
    return reachable


def _snap_penalty(candidate: dict, network: dict) -> float:
    if network["route_cost"] == "distance":
        return candidate["snap_distance_m"]
    return candidate["snap_distance_m"] / network["snap_access_speed_m_s"]


def _least_cost_candidate_path(
    graph: nx.DiGraph,
    sources: list[dict],
    targets: list[dict],
    network: dict,
) -> tuple[dict, dict, list[str]]:
    """Find the best source/target link pair with one targeted Dijkstra search.

    The heap is seeded at every candidate departure link.  It stops once no
    unsettled network path can improve the best reached arrival candidate, so
    it never constructs a full path dictionary for the complete network graph.
    """
    targets_by_node: dict[str, list[dict]] = {}
    for candidate in targets:
        targets_by_node.setdefault(candidate["from"], []).append(candidate)

    distances: dict[str, float] = {}
    predecessors: dict[str, str] = {}
    origins: dict[str, dict] = {}
    order = itertools.count()
    heap: list[tuple[float, int, str]] = []
    for candidate in sources:
        node = candidate["to"]
        cost = _snap_penalty(candidate, network)
        previous = distances.get(node)
        if previous is None or cost < previous:
            distances[node] = cost
            origins[node] = candidate
            heapq.heappush(heap, (cost, next(order), node))

    winner: tuple[float, dict, dict, str] | None = None
    while heap:
        distance, _, node = heapq.heappop(heap)
        if distance != distances.get(node):
            continue
        if winner is not None and distance > winner[0]:
            break

        for target in targets_by_node.get(node, []):
            total = distance + _snap_penalty(target, network)
            if winner is None or (
                total,
                target["snap_distance_m"],
                origins[node]["snap_distance_m"],
                target["id"],
                origins[node]["id"],
            ) < (
                winner[0],
                winner[2]["snap_distance_m"],
                winner[1]["snap_distance_m"],
                winner[2]["id"],
                winner[1]["id"],
            ):
                winner = (total, origins[node], target, node)

        for next_node, edge in graph[node].items():
            proposal = distance + edge["weight"]
            if proposal < distances.get(next_node, math.inf):
                distances[next_node] = proposal
                predecessors[next_node] = node
                origins[next_node] = origins[node]
                heapq.heappush(heap, (proposal, next(order), next_node))

    if winner is None:
        raise nx.NetworkXNoPath

    _, source, target, target_node = winner
    nodes = [target_node]
    while nodes[-1] in predecessors:
        nodes.append(predecessors[nodes[-1]])
    nodes.reverse()
    return source, target, _links_for_node_path(graph, nodes)


def _resolve_service_route(
    service: dict,
    supply: dict,
    graph: nx.DiGraph,
    mode_links: list[dict],
    fixed_stop_links: dict[str, dict],
) -> tuple[list[str], dict[str, dict]]:
    """Choose direction-feasible stop links and the least-cost route between them."""
    radius = supply["network"]["stop_snap_radius_m"]
    candidate_sets = []
    for stop_id in service["stops"]:
        if stop_id in fixed_stop_links:
            candidates = [fixed_stop_links[stop_id]]
        else:
            candidates = _stop_candidates(supply["stops_by_id"][stop_id], mode_links, radius)
        if not candidates:
            raise TransportConfigError(
                f"No {service['network_mode']!r} network link found within {radius:.0f} m "
                f"of stop {stop_id}."
            )
        candidate_sets.append(candidates)

    # The geometrically nearest link can be the opposite one-way track. Work
    # backwards so every retained candidate can reach at least one candidate
    # at every following stop (important for services with more than 2 stops).
    for index in range(len(candidate_sets) - 2, -1, -1):
        reverse_reachable = _reverse_reachable_nodes(
            graph,
            {candidate["from"] for candidate in candidate_sets[index + 1]},
        )
        candidate_sets[index] = [
            candidate
            for candidate in candidate_sets[index]
            if candidate["to"] in reverse_reachable
        ]
        if not candidate_sets[index]:
            raise TransportConfigError(
                f"No direction-feasible {service['network_mode']!r} departure link "
                f"was found for service {service['id']} stop {service['stops'][index]}."
            )

    # One targeted shortest-path search is sufficient for each service
    # segment. Only the first stop has multiple departure candidates; after a
    # segment the selected arrival link becomes the next departure link.
    choices: list[dict] = []
    route: list[str] = []
    sources = candidate_sets[0][: supply["network"]["stop_candidate_limit"]]
    for index, targets in enumerate(candidate_sets[1:]):
        try:
            source, target, connecting_links = _least_cost_candidate_path(
                graph, sources, targets, supply["network"]
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            raise TransportConfigError(
                f"No directed {service['network_mode']!r} path connects the configured "
                f"stops for service {service['id']}."
            )
        if index == 0:
            choices.append(source)
            route.append(source["id"])
        route.extend(connecting_links)
        if not route or route[-1] != target["id"]:
            route.append(target["id"])
        choices.append(target)
        sources = [target]

    assignments = dict(zip(service["stops"], choices))
    return route, assignments


def _service_route_metrics(
    service: dict,
    route: list[str],
    assignments: dict[str, dict],
    mode_links: list[dict],
    vehicle_type: dict,
    tolerance_s: float,
) -> dict:
    """Measure each scheduled segment and reject physically impossible timing."""
    links_by_id = {link["id"]: link for link in mode_links}
    segments = []
    cursor = 0
    for index, (from_stop, to_stop) in enumerate(
        zip(service["stops"], service["stops"][1:])
    ):
        from_link = assignments[from_stop]["id"]
        to_link = assignments[to_stop]["id"]
        from_index = route.index(from_link, cursor)
        to_index = route.index(to_link, from_index + (from_link != to_link))
        # A vehicle traverses an intermediate stop link before arriving there;
        # do not count that same link again after its dwell/departure.
        first_index = from_index if index == 0 else from_index + 1
        segment_links = route[first_index : to_index + 1]
        length_m = sum(links_by_id[link_id]["length"] for link_id in segment_links)
        minimum_running_time_s = sum(
            links_by_id[link_id]["length"]
            / min(
                links_by_id[link_id]["freespeed"],
                vehicle_type["maximum_velocity_m_s"],
            )
            for link_id in segment_links
        )
        if service.get("_derive_travel_times"):
            scheduled_time_s = max(
                1.0,
                math.ceil(
                    minimum_running_time_s
                    * float(service.get("_running_time_multiplier", 1.0))
                    + float(service.get("_running_time_allowance_s", 0.0))
                ),
            )
            service["segment_travel_times_s"][index] = scheduled_time_s
        else:
            scheduled_time_s = service["segment_travel_times_s"][index]
        if minimum_running_time_s > scheduled_time_s + tolerance_s:
            raise TransportConfigError(
                f"Service {service['id']} segment {from_stop}->{to_stop} is scheduled "
                f"in {scheduled_time_s:.1f}s but needs at least "
                f"{minimum_running_time_s:.1f}s at network/vehicle free-flow speed."
            )
        segments.append(
            {
                "from_stop": from_stop,
                "to_stop": to_stop,
                "link_count": len(segment_links),
                "length_m": length_m,
                "minimum_running_time_s": minimum_running_time_s,
                "scheduled_time_s": scheduled_time_s,
                "operational_allowance_s": scheduled_time_s
                - minimum_running_time_s,
            }
        )
        cursor = to_index
    return {
        "link_count": len(route),
        "length_m": sum(segment["length_m"] for segment in segments),
        "minimum_running_time_s": sum(
            segment["minimum_running_time_s"] for segment in segments
        ),
        "scheduled_running_time_s": sum(
            segment["scheduled_time_s"] for segment in segments
        ),
        "segments": segments,
    }


def resolve_network_routes(network_file: Path, supply: dict) -> dict:
    """Snap configured facilities and route each service over existing links."""
    graphs, links_by_mode = _read_modal_network(Path(network_file), supply)
    fixed_stop_links: dict[str, dict] = {}
    route_links: dict[str, list[str]] = {}
    route_metrics: dict[str, dict] = {}
    stop_network_modes: dict[str, str] = {}
    for service in supply["services"]:
        for stop_id in service["stops"]:
            existing_mode = stop_network_modes.get(stop_id)
            if existing_mode is not None and existing_mode != service["network_mode"]:
                raise TransportConfigError(
                    f"Stop {stop_id} is shared by services mapped to different network modes. "
                    "Declare separate rail and bus facilities at the interchange."
                )
            stop_network_modes[stop_id] = service["network_mode"]
        route, assignments = _resolve_service_route(
            service,
            supply,
            graphs[service["network_mode"]],
            links_by_mode[service["network_mode"]],
            fixed_stop_links,
        )
        route_links[service["id"]] = route
        route_metrics[service["id"]] = _service_route_metrics(
            service,
            route,
            assignments,
            links_by_mode[service["network_mode"]],
            supply["vehicle_types_by_id"][service["vehicle_type"]],
            supply["validation"]["minimum_running_time_tolerance_s"],
        )
        fixed_stop_links.update(assignments)
    return {
        "nodes": [],
        "links": [],
        "stop_links": {
            stop_id: link["id"] for stop_id, link in fixed_stop_links.items()
        },
        "stop_snap_distances_m": {
            stop_id: link["snap_distance_m"]
            for stop_id, link in fixed_stop_links.items()
        },
        "route_links": route_links,
        "route_metrics": route_metrics,
    }


def build_pseudo_network(supply: dict) -> dict:
    """Resolve configured stops and services into MATSim nodes and links."""
    stops = supply["stops_by_id"]
    network_config = supply["network"]
    stop_modes = {stop_id: {"pt"} for stop_id in stops}
    for service in supply["services"]:
        for stop_id in service["stops"]:
            stop_modes[stop_id].add(service["mode"])

    nodes: list[dict] = []
    links: list[dict] = []
    stop_links: dict[str, str] = {}
    for stop_id, stop in stops.items():
        inbound_node = f"pt_node_{stop_id}_in"
        outbound_node = f"pt_node_{stop_id}_out"
        stop_link = f"pt_stop_link_{stop_id}"
        nodes.extend(
            [
                {"id": inbound_node, "x": stop["x"], "y": stop["y"]},
                {"id": outbound_node, "x": stop["x"], "y": stop["y"]},
            ]
        )
        links.append(
            {
                "id": stop_link,
                "from": inbound_node,
                "to": outbound_node,
                "length": network_config["stop_link_length_m"],
                "freespeed": network_config["stop_link_freespeed_m_s"],
                "capacity": network_config["capacity_veh_h"],
                "permlanes": 1.0,
                "modes": ",".join(sorted(stop_modes[stop_id])),
            }
        )
        stop_links[stop_id] = stop_link

    route_links: dict[str, list[str]] = {}
    for service in supply["services"]:
        sequence = [stop_links[service["stops"][0]]]
        vehicle_type = supply["vehicle_types_by_id"][service["vehicle_type"]]
        for index, (from_stop_id, to_stop_id) in enumerate(
            zip(service["stops"], service["stops"][1:])
        ):
            from_stop = stops[from_stop_id]
            to_stop = stops[to_stop_id]
            length = math.hypot(
                to_stop["x"] - from_stop["x"], to_stop["y"] - from_stop["y"]
            )
            if length <= 0:
                raise TransportConfigError(
                    f"Service {service['id']} has colocated consecutive stops "
                    f"{from_stop_id} and {to_stop_id}."
                )
            scheduled_time = service["segment_travel_times_s"][index]
            freespeed = (
                length
                / scheduled_time
                * network_config["connector_speed_margin"]
            )
            if freespeed > vehicle_type["maximum_velocity_m_s"]:
                raise TransportConfigError(
                    f"Service {service['id']} segment {from_stop_id}->{to_stop_id} "
                    f"requires {freespeed:.2f} m/s, above vehicle type "
                    f"{service['vehicle_type']} maximum {vehicle_type['maximum_velocity_m_s']:.2f} m/s."
                )
            connector_id = f"pt_connector_{service['id']}_{index}"
            links.append(
                {
                    "id": connector_id,
                    "from": f"pt_node_{from_stop_id}_out",
                    "to": f"pt_node_{to_stop_id}_in",
                    "length": length,
                    "freespeed": freespeed,
                    "capacity": network_config["capacity_veh_h"],
                    "permlanes": 1.0,
                    "modes": f"pt,{service['mode']}",
                }
            )
            sequence.extend((connector_id, stop_links[to_stop_id]))
        route_links[service["id"]] = sequence

    return {
        "nodes": nodes,
        "links": links,
        "stop_links": stop_links,
        "route_links": route_links,
    }


def _xml_line(tag: str, attributes: dict) -> str:
    element = ET.Element(tag, {key: str(value) for key, value in attributes.items()})
    return ET.tostring(element, encoding="unicode", short_empty_elements=True)


def augment_network(base_network: Path, output_network: Path, topology: dict) -> None:
    """Stream-copy a large MATSim network and inject transport nodes/links."""
    base_network = Path(base_network).resolve()
    output_network = Path(output_network).resolve()
    if not base_network.is_file():
        raise FileNotFoundError(f"Base network not found: {base_network}")
    if base_network == output_network:
        raise ValueError("Transport network output must differ from its base network input.")
    output_network.parent.mkdir(parents=True, exist_ok=True)

    generated_ids = {
        item["id"] for item in topology["nodes"] + topology["links"]
    }
    inserted_nodes = False
    inserted_links = False
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_network.name}.", suffix=".tmp", dir=output_network.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        with base_network.open("r", encoding="utf-8") as source, temporary_path.open(
            "w", encoding="utf-8", newline=""
        ) as destination:
            for line in source:
                if any(f'id="{generated_id}"' in line for generated_id in generated_ids):
                    raise TransportConfigError(
                        "The base network already contains a generated Module 3 node or link id."
                    )
                stripped = line.strip()
                if stripped == "</nodes>":
                    for node in topology["nodes"]:
                        destination.write(f"    {_xml_line('node', node)}\n")
                    inserted_nodes = True
                elif stripped == "</links>":
                    for link in topology["links"]:
                        attributes = {
                            "id": link["id"],
                            "from": link["from"],
                            "to": link["to"],
                            "length": link["length"],
                            "freespeed": link["freespeed"],
                            "capacity": link["capacity"],
                            "permlanes": link.get("permlanes", 1.0),
                            "modes": link["modes"],
                        }
                        destination.write(f"    {_xml_line('link', attributes)}\n")
                    inserted_links = True
                destination.write(line)
        if not inserted_nodes or not inserted_links:
            raise TransportConfigError(
                f"Could not find MATSim <nodes> and <links> sections in {base_network}."
            )
        os.replace(temporary_path, output_network)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()



"""MATSim XML and resolved-manifest writers for Module 3."""


import json
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom



def _pretty_xml(root: ET.Element, doctype: str) -> str:
    body = minidom.parseString(ET.tostring(root, encoding="utf-8")).toprettyxml(
        indent="  "
    )
    body = body.split("\n", 1)[1]
    return f'<?xml version="1.0" encoding="utf-8"?>\n{doctype}\n{body}'


def service_departures(service: dict) -> list[tuple[str, float, str]]:
    """Create one vehicle per departure for the advanced compatibility schema."""
    result = []
    departure_time = service["service_start_s"]
    index = 1
    while departure_time <= service["service_end_s"] + 1e-9:
        departure_id = f"departure_{service['id']}_{index}"
        vehicle_id = f"pt_vehicle_{service['id']}_{index}"
        result.append((departure_id, departure_time, vehicle_id))
        departure_time += service["headway_s"]
        index += 1
    return result


def _scheduled_times(service: dict) -> list[float]:
    times = []
    departure_time = service["service_start_s"]
    while departure_time <= service["service_end_s"] + 1e-9:
        times.append(departure_time)
        departure_time += service["headway_s"]
    return times


def build_departure_plan(
    supply: dict,
) -> dict[str, list[tuple[str, float, str]]]:
    """Assign compact services to a reusable, location-aware physical fleet."""
    services_by_id = supply["services_by_id"]
    departures = {
        service["id"]: service_departures(service)
        for service in supply["services"]
        if not service.get("circulation_id")
    }

    for fleet in supply.get("circulation_fleets", []):
        fleet_id = fleet["id"]
        services = [services_by_id[service_id] for service_id in fleet["service_ids"]]
        terminals = sorted({service["origin_terminal"] for service in services})
        if len(services) != 2 or len(terminals) != 2:
            raise TransportConfigError(
                f"Circulation {fleet_id} requires one service in each direction."
            )

        ready_at: dict[str, list[tuple[float, str]]] = {
            terminal: [] for terminal in terminals
        }
        for index in range(1, fleet["vehicle_count"] + 1):
            terminal = terminals[(index - 1) % len(terminals)]
            heapq.heappush(
                ready_at[terminal],
                (0.0, f"pt_vehicle_{fleet_id}_{index}"),
            )

        events = []
        for service in services:
            departures[service["id"]] = []
            for index, departure_time in enumerate(_scheduled_times(service), start=1):
                events.append((departure_time, service["id"], index))

        for departure_time, service_id, index in sorted(events):
            service = services_by_id[service_id]
            origin = service["origin_terminal"]
            destination = service["destination_terminal"]
            if not ready_at[origin] or ready_at[origin][0][0] > departure_time + 1e-9:
                next_ready = ready_at[origin][0][0] if ready_at[origin] else None
                detail = (
                    f"next vehicle is ready at {matsim_time(next_ready)}"
                    if next_ready is not None
                    else "no vehicle is positioned there"
                )
                raise TransportConfigError(
                    f"{fleet['vehicle_count']} {fleet['mode']} vehicles cannot sustain "
                    f"the requested {service['headway_s'] / 60:.1f}-minute frequency "
                    f"for {fleet_id}; {detail}. Increase number_of_vehicles or reduce "
                    "the frequency."
                )
            _, vehicle_id = heapq.heappop(ready_at[origin])
            departure_id = f"departure_{service_id}_{index}"
            departures[service_id].append(
                (departure_id, departure_time, vehicle_id)
            )
            running_time = sum(service["segment_travel_times_s"]) + sum(
                service["dwell_times_s"][1:-1]
            )
            heapq.heappush(
                ready_at[destination],
                (departure_time + running_time + service["layover_s"], vehicle_id),
            )
    return departures


def write_transit_schedule(
    supply: dict, topology: dict, output_file: Path
) -> dict[str, list[tuple[str, float, str]]]:
    root = ET.Element("transitSchedule")
    stops_element = ET.SubElement(root, "transitStops")
    for stop in supply["stops"]:
        ET.SubElement(
            stops_element,
            "stopFacility",
            id=stop["id"],
            x=str(stop["x"]),
            y=str(stop["y"]),
            linkRefId=topology["stop_links"][stop["id"]],
            name=stop["name"],
            isBlocking="false",
        )

    transfers = supply.get("transfers", [])
    if transfers:
        transfer_element = ET.SubElement(root, "minimalTransferTimes")
        for transfer in transfers:
            ET.SubElement(
                transfer_element,
                "relation",
                fromStop=transfer["from_stop"],
                toStop=transfer["to_stop"],
                transferTime=str(transfer["transfer_time_s"]),
            )

    departures_by_service = build_departure_plan(supply)
    for service in supply["services"]:
        line = ET.SubElement(
            root, "transitLine", id=f"line_{service['id']}", name=service["name"]
        )
        route = ET.SubElement(line, "transitRoute", id=f"route_{service['id']}")
        ET.SubElement(route, "description").text = service["name"]
        ET.SubElement(route, "transportMode").text = service["mode"]
        profile = ET.SubElement(route, "routeProfile")
        cumulative = 0.0
        for index, stop_id in enumerate(service["stops"]):
            attributes = {"refId": stop_id, "awaitDeparture": "true"}
            if index == 0:
                attributes["departureOffset"] = matsim_time(0.0)
            else:
                cumulative += service["segment_travel_times_s"][index - 1]
                attributes["arrivalOffset"] = matsim_time(cumulative)
                if index < len(service["stops"]) - 1:
                    cumulative += service["dwell_times_s"][index]
                    attributes["departureOffset"] = matsim_time(cumulative)
            ET.SubElement(profile, "stop", **attributes)
        network_route = ET.SubElement(route, "route")
        for link_id in topology["route_links"][service["id"]]:
            ET.SubElement(network_route, "link", refId=link_id)
        departures = ET.SubElement(route, "departures")
        service_rows = departures_by_service[service["id"]]
        for departure_id, departure_time, vehicle_id in service_rows:
            ET.SubElement(
                departures,
                "departure",
                id=departure_id,
                departureTime=matsim_time(departure_time),
                vehicleRefId=vehicle_id,
            )

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        _pretty_xml(
            root,
            '<!DOCTYPE transitSchedule SYSTEM "http://www.matsim.org/files/dtd/transitSchedule_v2.dtd">',
        ),
        encoding="utf-8",
    )
    return departures_by_service


def write_transit_vehicles(
    supply: dict,
    departures_by_service: dict[str, list[tuple[str, float, str]]],
    output_file: Path,
) -> None:
    namespace = "http://www.matsim.org/files/dtd"
    xsi = "http://www.w3.org/2001/XMLSchema-instance"
    ET.register_namespace("", namespace)
    ET.register_namespace("xsi", xsi)
    root = ET.Element(
        f"{{{namespace}}}vehicleDefinitions",
        {
            f"{{{xsi}}}schemaLocation": (
                f"{namespace} {namespace}/vehicleDefinitions_v2.0.xsd"
            )
        },
    )
    for vehicle_type in supply["vehicle_types"]:
        element = ET.SubElement(
            root, f"{{{namespace}}}vehicleType", id=vehicle_type["id"]
        )
        ET.SubElement(
            element,
            f"{{{namespace}}}capacity",
            seats=str(vehicle_type["seats"]),
            standingRoomInPersons=str(vehicle_type["standing_room"]),
        )
        ET.SubElement(
            element, f"{{{namespace}}}length", meter=str(vehicle_type["length_m"])
        )
        ET.SubElement(
            element, f"{{{namespace}}}width", meter=str(vehicle_type["width_m"])
        )
        ET.SubElement(
            element,
            f"{{{namespace}}}maximumVelocity",
            meterPerSecond=str(vehicle_type["maximum_velocity_m_s"]),
        )
        ET.SubElement(
            element,
            f"{{{namespace}}}passengerCarEquivalents",
            pce=str(vehicle_type["passenger_car_equivalents"]),
        )
        ET.SubElement(
            element,
            f"{{{namespace}}}networkMode",
            networkMode=supply["network"]["mode_map"][vehicle_type["mode"]],
        )
    vehicle_types_by_id: dict[str, str] = {}
    for fleet in supply.get("circulation_fleets", []):
        for index in range(1, fleet["vehicle_count"] + 1):
            vehicle_types_by_id[f"pt_vehicle_{fleet['id']}_{index}"] = fleet[
                "vehicle_type"
            ]
    for service in supply["services"]:
        for _, _, vehicle_id in departures_by_service[service["id"]]:
            existing_type = vehicle_types_by_id.setdefault(
                vehicle_id, service["vehicle_type"]
            )
            if existing_type != service["vehicle_type"]:
                raise TransportConfigError(
                    f"Transit vehicle {vehicle_id} is assigned conflicting vehicle types."
                )
    for vehicle_id, vehicle_type in sorted(vehicle_types_by_id.items()):
        ET.SubElement(
            root,
            f"{{{namespace}}}vehicle",
            id=vehicle_id,
            type=vehicle_type,
        )

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    xml = minidom.parseString(ET.tostring(root, encoding="utf-8")).toprettyxml(
        indent="  ", encoding="utf-8"
    )
    output_file.write_bytes(xml)


def write_manifest(manifest: dict, output_file: Path) -> None:
    """Write YAML when PyYAML is available, otherwise valid JSON-style YAML."""
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml

        text = yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True)
    except ImportError:
        # YAML 1.2 is a superset of JSON, so this remains a valid YAML document.
        text = json.dumps(manifest, indent=2, ensure_ascii=False)
    output_file.write_text(text, encoding="utf-8")



"""Generate the MATSim-UAM fleet as part of Module 3 transport supply."""

from pathlib import Path

import config
from uam_geometry import vertiport_geometry
from xml_writer import writematsimvehicles


class UAMFleetGenerator:
    def __init__(self):
        self.fleet_size = int(config.FLEET_SIZE)
        self.vehicle_type = config.UAM_VEHICLE_TYPE
        self.design_rules = config.VERTIPORT_DESIGN_RULES
        self.vertiports = config.VERTIPORTS

    def generate(self, output_file: Path) -> Path:
        if not self.vertiports:
            raise ValueError("Cannot generate a UAM fleet without vertiports.")

        vehicles = []
        remaining = self.fleet_size
        vehicle_id = 1
        print(f"[Module 3] Generating {self.fleet_size} physical eVTOLs...")
        for vertiport in self.vertiports:
            geometry = vertiport_geometry(
                vertiport, self.vehicle_type, self.design_rules
            )
            spawn_count = min(len(geometry["stands"]), remaining)
            for _ in range(spawn_count):
                vehicles.append(
                    {
                        "id": str(vehicle_id),
                        "type": self.vehicle_type["id"],
                        "station_id": str(vertiport["id"]),
                    }
                )
                vehicle_id += 1
            remaining -= spawn_count
            print(
                f"- Vertiport {vertiport['id']}: {spawn_count} vehicles "
                f"across {len(geometry['stands'])} stands"
            )
            if remaining == 0:
                break
        if remaining:
            raise ValueError(
                f"Fleet exceeds physical stand capacity by {remaining} vehicles. "
                "Add stands or reduce FLEET_SIZE."
            )

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        writematsimvehicles(
            self.vertiports,
            self.vehicle_type,
            vehicles,
            str(output_path),
        )
        return output_path



"""Cross-file validation for the generated Module 3 transport supply."""


from pathlib import Path
import xml.etree.ElementTree as ET



def validate_generated_supply(
    network_file: Path,
    schedule_file: Path,
    vehicles_file: Path,
    uam_fleet_file: Path,
) -> None:
    for label, path in (
        ("transport network", network_file),
        ("transit schedule", schedule_file),
        ("transit vehicles", vehicles_file),
        ("UAM fleet", uam_fleet_file),
    ):
        if not Path(path).is_file() or Path(path).stat().st_size == 0:
            raise TransportConfigError(f"Generated {label} is missing or empty: {path}")

    schedule_root = ET.parse(schedule_file).getroot()
    stop_links = {
        stop.get("linkRefId")
        for stop in schedule_root.findall("./transitStops/stopFacility")
    }
    route_links = {
        link.get("refId")
        for link in schedule_root.findall("./transitLine/transitRoute/route/link")
    }
    required_links = stop_links | route_links
    found_links = set()
    for _, element in ET.iterparse(network_file, events=("end",)):
        if element.tag.rsplit("}", 1)[-1] == "link":
            link_id = element.get("id")
            if link_id in required_links:
                found_links.add(link_id)
        element.clear()
    missing_links = sorted(required_links - found_links)
    if missing_links:
        raise TransportConfigError(
            "Transit schedule references missing network links: "
            + ", ".join(missing_links[:10])
        )

    namespace = {"v": "http://www.matsim.org/files/dtd"}
    vehicle_root = ET.parse(vehicles_file).getroot()
    vehicle_ids = {
        vehicle.get("id") for vehicle in vehicle_root.findall("v:vehicle", namespace)
    }
    departure_vehicle_ids = {
        departure.get("vehicleRefId")
        for departure in schedule_root.findall(
            "./transitLine/transitRoute/departures/departure"
        )
    }
    missing_vehicles = sorted(departure_vehicle_ids - vehicle_ids)
    if missing_vehicles:
        raise TransportConfigError(
            "Transit departures reference missing vehicles: "
            + ", ".join(missing_vehicles[:10])
        )



"""Orchestrate all scheduled PT and UAM supply artifacts for Module 3."""


from dataclasses import dataclass
from pathlib import Path

import config



@dataclass(frozen=True)
class TransportSupplyPaths:
    network: Path
    transit_schedule: Path
    transit_vehicles: Path
    uam_fleet: Path
    manifest: Path


class TransportSupplyGenerator:
    def __init__(self, settings: dict | None = None):
        self.settings = normalise_transport_config(
            settings if settings is not None else config.TRANSPORT_SUPPLY
        )

    def generate(
        self,
        *,
        base_network: Path,
        network_output: Path | None = None,
        output_directory: Path | None = None,
    ) -> TransportSupplyPaths:
        if not self.settings.get("enabled", True):
            raise ValueError("Module 3 transport supply is disabled in config.py.")

        project_root = Path(__file__).resolve().parents[1]
        output_directory = Path(
            output_directory
            or project_root
            / "scenarios"
            / self.settings.get("output_directory", "transport")
        ).resolve()
        base_network = Path(base_network).resolve()
        if self.settings["network"]["strategy"] == "pseudo_network":
            network_output = Path(
                network_output
                or project_root
                / "scenarios"
                / "networks"
                / self.settings.get("network_output_file", "network_transport.xml")
            ).resolve()
        else:
            network_output = base_network
        paths = TransportSupplyPaths(
            network=network_output,
            transit_schedule=output_directory
            / self.settings.get("transit_schedule_file", "transit_schedule.xml"),
            transit_vehicles=output_directory
            / self.settings.get("transit_vehicles_file", "transit_vehicles.xml"),
            uam_fleet=output_directory
            / self.settings.get("uam_fleet_file", "uam_fleet.xml"),
            manifest=output_directory
            / self.settings.get("manifest_file", "resolved_transport_supply.yaml"),
        )

        print("--- Module 3: TransportSupplyGenerator initiated ---")
        if self.settings["network"]["strategy"] == "network":
            topology = resolve_network_routes(base_network, self.settings)
        else:
            topology = build_pseudo_network(self.settings)
            augment_network(base_network, paths.network, topology)
        departures = write_transit_schedule(
            self.settings, topology, paths.transit_schedule
        )
        write_transit_vehicles(
            self.settings, departures, paths.transit_vehicles
        )
        UAMFleetGenerator().generate(paths.uam_fleet)

        manifest = {
            "module": 3,
            "input_mode": self.settings.get("input_mode"),
            "data_status": self.settings.get("data_status", "unspecified"),
            "files": {
                "network": str(paths.network),
                "transit_schedule": str(paths.transit_schedule),
                "transit_vehicles": str(paths.transit_vehicles),
                "uam_fleet": str(paths.uam_fleet),
            },
            "circulation_fleets": [
                {
                    "id": fleet["id"],
                    "mode": fleet["mode"],
                    "physical_vehicle_count": fleet["vehicle_count"],
                    "vehicle_type": fleet["vehicle_type"],
                    "services": fleet["service_ids"],
                }
                for fleet in self.settings.get("circulation_fleets", [])
            ],
            "stops": [
                {
                    "id": stop["id"],
                    "name": stop["name"],
                    "x": stop["x"],
                    "y": stop["y"],
                    "link_id": topology["stop_links"][stop["id"]],
                    "snap_distance_m": topology.get(
                        "stop_snap_distances_m", {}
                    ).get(stop["id"], 0.0),
                }
                for stop in self.settings["stops"]
            ],
            "services": [
                {
                    "id": service["id"],
                    "name": service["name"],
                    "mode": service["mode"],
                    "stops": service["stops"],
                    "network_links": topology["route_links"][service["id"]],
                    "route_metrics": topology.get("route_metrics", {}).get(
                        service["id"]
                    ),
                    "departure_count": len(departures[service["id"]]),
                    "first_departure": service["service_start"],
                    "last_departure": service["service_end"],
                    "headway_s": service["headway_s"],
                    "vehicle_type": service["vehicle_type"],
                    "circulation_id": service.get("circulation_id"),
                    "layover_s": service.get("layover_s"),
                }
                for service in self.settings["services"]
            ],
        }
        write_manifest(manifest, paths.manifest)
        validate_generated_supply(
            paths.network,
            paths.transit_schedule,
            paths.transit_vehicles,
            paths.uam_fleet,
        )
        print(f"[Module 3] Transport network: {paths.network}")
        print(f"[Module 3] Transit schedule: {paths.transit_schedule}")
        print(f"[Module 3] Transit vehicles: {paths.transit_vehicles}")
        print(f"[Module 3] UAM fleet: {paths.uam_fleet}")
        print(f"[Module 3] Resolved manifest: {paths.manifest}")
        return paths



"""Run Module 3 directly with the configured scenario paths."""

from pathlib import Path



def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    paths = TransportSupplyGenerator().generate(
        base_network=project_root
        / "scenarios"
        / "networks"
        / "network_with_uam.xml",
        network_output=project_root
        / "scenarios"
        / "networks"
        / "network_transport.xml",
        output_directory=project_root / "scenarios" / "transport",
    )
    print("--- Module 3 complete ---")
    print(paths)


if __name__ == "__main__":
    main()
