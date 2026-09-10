"""Module 5 MATSim analytics extraction and local dashboard server."""

from __future__ import annotations

"""Build browser-ready analytics from MATSim output files.

The extractor deliberately reads MATSim XML as a stream.  A complete events
file can be very large, while Module 5 only needs link traversals, passenger
state changes, and a small subset of activity events.
"""


import bisect
import gzip
import hashlib
import heapq
import importlib
import json
import math
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator


SCHEMA_VERSION = 8
QUEUE_INTERVAL_SECONDS = 30

PT_MODES = frozenset(
    {
        "pt",
        "rail",
        "train",
        "bus",
        "tram",
        "subway",
        "metro",
        "ferry",
    }
)

CUSTOM_LINK_PREFIXES = (
    "link_passenger_",
    "link_security_",
    "link_gate_",
    "link_stand_",
    "link_apron_",
    "link_fato_",
    "link_airroute_",
    "link_base_to_vt_",
    "link_vt_to_base_",
)

VERTIPORT_NODE_PATTERN = re.compile(
    r"^vt_(?:terminal|security|gate|apron|airborne_dummy|stand|fato)_(\d+)(?:_|$)"
)


@dataclass(frozen=True)
class ExtractionPaths:
    """Input and output paths used by one analytics extraction."""

    events: Path
    network: Path
    design_report: Path
    population: Path | None
    output_dir: Path
    background_traffic_enabled: bool = False


@dataclass
class LinkSegment:
    vehicle_id: str
    session_id: int
    link_id: str
    start_time: float
    end_time: float
    mode: str


@dataclass
class WalkLeg:
    person_id: str
    session_id: int
    start_link_id: str
    end_link_id: str
    start_time: float
    end_time: float


@dataclass
class LinkRecord:
    link_id: str
    from_node: str
    to_node: str
    length: float
    freespeed: float
    capacity: float
    modes: str


@dataclass(frozen=True)
class FatoMovement:
    """One observed use of a specific physical FATO resource."""

    time: float
    vertiport_id: str
    fato_id: str
    vehicle_id: str
    movement_type: str


def _open_binary(path: Path):
    return gzip.open(path, "rb") if path.suffix.lower() == ".gz" else path.open("rb")


def _iter_elements(path: Path, tag: str) -> Iterator[ET.Element]:
    with _open_binary(path) as stream:
        for _, element in ET.iterparse(stream, events=("end",)):
            if element.tag.rsplit("}", 1)[-1] == tag:
                yield element
            element.clear()


def _as_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _is_walk_mode(mode: str | None) -> bool:
    return bool(mode and "walk" in mode.lower())


def _allows_walk(modes: str) -> bool:
    return any(
        mode == "walk" or mode.endswith("_walk")
        for mode in re.split(r"[,;\s]+", modes.lower())
        if mode
    )


def _allows_surface_walk_route(modes: str) -> bool:
    tokens = {
        mode
        for mode in re.split(r"[,;\s]+", modes.lower())
        if mode
    }
    return _allows_walk(modes) or "car" in tokens


def _vehicle_travel_mode(
    vehicle_id: str,
    network_mode: str | None,
    transit_vehicles: set[str],
) -> str:
    """Map MATSim vehicle metadata to a visible playback transport mode."""

    identity = vehicle_id.lower()
    if identity.startswith(("uam_", "evtol_")):
        return "uam"
    if "rail" in identity or "train" in identity:
        return "train"
    if "bus" in identity:
        return "bus"
    if vehicle_id in transit_vehicles or (network_mode or "").lower() in PT_MODES:
        return "pt"
    return "car"


def _scheduled_vehicle_mode(attributes: dict[str, str]) -> str:
    identity = " ".join(
        attributes.get(key, "")
        for key in ("vehicle", "vehicleId", "transitLineId", "transitRouteId")
    ).lower()
    if "rail" in identity or "train" in identity:
        return "train"
    if "bus" in identity:
        return "bus"
    return "pt"


def _journey_outcome(observed_leg_modes: set[str], completed_uam: bool) -> str:
    """Classify a traveller from executed events, not their plan alternatives."""

    if completed_uam:
        return "uam"
    normalized = {mode.lower() for mode in observed_leg_modes}
    if normalized & PT_MODES:
        return "pt"
    if "car" in normalized:
        return "car"
    return "unobserved"


def _source_signature(paths: Iterable[Path], *, salt: str = "") -> str:
    digest = hashlib.sha256()
    for path in paths:
        stat = path.stat()
        digest.update(str(path.resolve()).encode("utf-8"))
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
    digest.update(salt.encode("utf-8"))
    return digest.hexdigest()[:16]


def _runtime_config() -> Any | None:
    try:
        return importlib.import_module("config")
    except (ImportError, AttributeError):
        return None


def _population_profiles(
    path: Path | None,
) -> tuple[dict[str, str], set[str], set[str]]:
    """Return urgency, UAM eligibility, and background-traffic people."""

    urgency: dict[str, str] = {}
    uam_eligible: set[str] = set()
    background_people: set[str] = set()
    if path is None or not path.exists():
        return urgency, uam_eligible, background_people

    with _open_binary(path) as stream:
        for _, person in ET.iterparse(stream, events=("end",)):
            if person.tag.rsplit("}", 1)[-1] != "person":
                continue

            person_id = person.attrib.get("id", "")
            if not person_id:
                person.clear()
                continue

            for attribute in person.iter():
                if (
                    attribute.tag.rsplit("}", 1)[-1] == "attribute"
                    and attribute.attrib.get("name") == "subpopulation"
                ):
                    urgency[person_id] = (attribute.text or "unclassified").strip()
                if (
                    attribute.tag.rsplit("}", 1)[-1] == "attribute"
                    and attribute.attrib.get("name") == "backgroundTraffic"
                    and (attribute.text or "").strip().lower() == "true"
                ):
                    background_people.add(person_id)

            if person_id.startswith("background_car_"):
                background_people.add(person_id)

            if any(
                child.tag.rsplit("}", 1)[-1] == "leg"
                and child.attrib.get("mode") == "uam"
                for child in person.iter()
            ):
                uam_eligible.add(person_id)

            person.clear()

    return urgency, uam_eligible, background_people


def _point_line_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    if start == end:
        return math.dist(point, start)
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    fraction = (
        (point[0] - start[0]) * dx + (point[1] - start[1]) * dy
    ) / (dx * dx + dy * dy)
    fraction = max(0.0, min(1.0, fraction))
    projection = (start[0] + fraction * dx, start[1] + fraction * dy)
    return math.dist(point, projection)


def _rdp_indices(points: list[tuple[float, float]], tolerance: float) -> list[int]:
    """Return Ramer-Douglas-Peucker indices while retaining original timing."""

    if len(points) <= 2:
        return list(range(len(points)))

    keep = {0, len(points) - 1}
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        maximum = 0.0
        selected = None
        for index in range(first + 1, last):
            distance = _point_line_distance(points[index], points[first], points[last])
            if distance > maximum:
                maximum = distance
                selected = index
        if selected is not None and maximum > tolerance:
            keep.add(selected)
            stack.append((first, selected))
            stack.append((selected, last))
    return sorted(keep)


def _bounded_indices(indices: list[int], maximum: int) -> list[int]:
    if len(indices) <= maximum:
        return indices
    selected = {
        indices[round(position * (len(indices) - 1) / (maximum - 1))]
        for position in range(maximum)
    }
    return sorted(selected)


class AnalyticsExtractor:
    """Extract trajectories, queues, KPIs, and vertiport geometry."""

    def __init__(
        self,
        paths: ExtractionPaths,
        *,
        crs: str | None = None,
        queue_interval_seconds: int = QUEUE_INTERVAL_SECONDS,
    ) -> None:
        self.paths = paths
        runtime_config = _runtime_config()
        configured_crs = (
            getattr(runtime_config, "MODULE5_CRS", "")
            if runtime_config is not None
            else ""
        )
        self.crs = str(crs or configured_crs).strip()
        if not self.crs:
            raise ValueError(
                "Module 5 requires the scenario network CRS. Set MODULE5_CRS "
                "in config.py or pass --crs."
            )
        self.queue_interval_seconds = max(1, int(queue_interval_seconds))
        self.warnings: list[str] = []

    def is_current(self) -> bool:
        manifest_path = self.paths.output_dir / "manifest.json"
        bundle_path = self.paths.output_dir / "analytics_bundle.json"
        if not manifest_path.exists() or not bundle_path.exists():
            return False
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return (
            manifest.get("schemaVersion") == SCHEMA_VERSION
            and manifest.get("sourceSignature") == self._signature()
        )

    def _signature(self) -> str:
        sources = [
            self.paths.events,
            self.paths.network,
            self.paths.design_report,
        ]
        if self.paths.population and self.paths.population.exists():
            sources.append(self.paths.population)
        return _source_signature(
            sources,
            salt=(
                "backgroundTrafficEnabled="
                f"{self.paths.background_traffic_enabled}"
            ),
        )

    def extract(self, *, force: bool = False) -> Path:
        self._validate_inputs()
        self.paths.output_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = self.paths.output_dir / "analytics_bundle.json"
        if not force and self.is_current():
            return bundle_path

        urgency, uam_eligible, background_people = _population_profiles(
            self.paths.population
        )
        if not self.paths.background_traffic_enabled:
            background_people.clear()
        event_data = self._read_events(
            urgency, uam_eligible, background_people
        )
        link_records, nodes = self._read_network(event_data["used_links"])
        transformer = self._coordinate_transformer()

        trajectories = self._build_trajectories(
            event_data["segments"],
            event_data["occupancy_events"],
            event_data["background_vehicles"],
            link_records,
            nodes,
            transformer,
        )
        trajectories.extend(
            self._build_walk_trajectories(
                event_data["walk_legs"],
                background_people,
                link_records,
                nodes,
                transformer,
            )
        )
        trajectories.sort(key=lambda item: (item["startTime"], item["id"]))
        vertiports = self._build_vertiports(link_records, nodes, transformer)
        landmarks = self._build_landmarks(transformer)
        queue_series = self._build_queue_series(
            event_data["stage_deltas"],
            event_data["start_time"],
            event_data["end_time"],
        )
        fato_occupancy_by_vertiport = []
        for vertiport in vertiports:
            vertiport_id = str(vertiport["id"])
            facility_occupancy_series = self._build_fato_occupancy_series(
                event_data["fato_stage_deltas_by_vertiport"].get(
                    vertiport_id, []
                ),
                event_data["start_time"],
                event_data["end_time"],
            )
            fato_occupancy_by_vertiport.append(
                {
                    "vertiportId": vertiport_id,
                    "name": vertiport["name"],
                    "series": facility_occupancy_series,
                }
            )
        capacity = self._build_capacity(
            event_data["fato_movements"],
            event_data["start_time"],
            event_data["end_time"],
        )
        outcomes = self._build_outcomes(
            event_data=event_data,
            urgency=urgency,
            uam_eligible=uam_eligible,
        )

        geographic_points = [
            coordinate
            for trajectory in trajectories
            for coordinate in trajectory["path"]
        ] + [landmark["position"] for landmark in landmarks]
        bounds = self._bounds(geographic_points)

        generated_at = datetime.now(timezone.utc).isoformat()
        run_id = f"{self.paths.events.parent.name}-{self._signature()}"
        bundle = {
            "schemaVersion": SCHEMA_VERSION,
            "run": {
                "id": run_id,
                "iteration": self._iteration_number(),
                "generatedAt": generated_at,
                "sourceSignature": self._signature(),
                "eventsFile": self.paths.events.name,
                "networkFile": self.paths.network.name,
                "crs": self.crs,
                "startTime": event_data["start_time"],
                "endTime": event_data["end_time"],
                "durationSeconds": max(
                    0.0, event_data["end_time"] - event_data["start_time"]
                ),
                "eventCount": event_data["event_count"],
                "eventTypes": dict(event_data["event_types"]),
                "warnings": self.warnings,
                "backgroundTrafficEnabled": self.paths.background_traffic_enabled,
            },
            "bounds": bounds,
            "landmarks": landmarks,
            "trajectories": trajectories,
            "queueStages": [
                {
                    "key": "terminalProcessing",
                    "label": "Terminal processing",
                    "unit": "passengers",
                    "definition": (
                        "Passengers between vertiport entry and boarding activity."
                    ),
                },
                {
                    "key": "uamDispatch",
                    "label": "UAM dispatch queue",
                    "unit": "passengers",
                    "definition": (
                        "Passengers between the MATSim passenger-waiting and "
                        "passenger-picked-up events."
                    ),
                },
                {
                    "key": "boardingHold",
                    "label": "Picked-up awaiting departure",
                    "unit": "passengers",
                    "definition": (
                        "Picked-up passengers waiting for their assigned eVTOL "
                        "to enter traffic."
                    ),
                },
                {
                    "key": "fatoOccupancy",
                    "label": "FATO occupancy",
                    "unit": "aircraft",
                    "definition": "Aircraft occupying take-off or landing FATO links.",
                },
            ],
            "queueSeries": queue_series,
            "fatoOccupancyByVertiport": fato_occupancy_by_vertiport,
            "waitTimes": event_data["wait_times"],
            "journeys": event_data["journeys"],
            "outcomes": outcomes,
            "capacity": capacity,
            "vertiports": vertiports,
        }

        bundle_path.write_text(
            json.dumps(bundle, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8",
        )
        manifest = {
            "schemaVersion": SCHEMA_VERSION,
            "runId": run_id,
            "generatedAt": generated_at,
            "sourceSignature": self._signature(),
            "bundle": bundle_path.name,
            "tables": self._write_tabular_exports(bundle),
            "warnings": self.warnings,
        }
        (self.paths.output_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        return bundle_path

    def _iteration_number(self) -> int | None:
        """Infer the MATSim iteration from an ITERS/it.N/N.events file."""

        parent_match = re.fullmatch(r"it\.(\d+)", self.paths.events.parent.name)
        file_match = re.match(r"(\d+)\.events\.xml(?:\.gz)?$", self.paths.events.name)
        if parent_match and file_match and parent_match.group(1) == file_match.group(1):
            return int(parent_match.group(1))
        return None

    def _validate_inputs(self) -> None:
        for label, path in (
            ("events", self.paths.events),
            ("network", self.paths.network),
            ("vertiport design report", self.paths.design_report),
        ):
            if not path.exists():
                raise FileNotFoundError(f"Module 5 {label} file not found: {path}")

    def _read_events(
        self,
        urgency: dict[str, str],
        uam_eligible: set[str],
        background_people: set[str],
    ) -> dict[str, Any]:
        event_types: Counter[str] = Counter()
        segments: list[LinkSegment] = []
        used_links: set[str] = set()
        active_link: dict[str, tuple[str, float, int, str]] = {}
        current_session: defaultdict[str, int] = defaultdict(int)
        vehicle_mode: dict[str, str] = {}
        transit_vehicles: set[str] = set()
        transit_drivers: set[str] = set()
        background_vehicles: set[str] = set()
        observed_leg_modes: defaultdict[str, set[str]] = defaultdict(set)
        stage_deltas: list[tuple[float, str, int]] = []
        fato_stage_deltas_by_vertiport: defaultdict[
            str, list[tuple[float, str, int]]
        ] = defaultdict(list)
        fato_active: dict[str, tuple[str, str, str, int]] = {}
        fato_passage: defaultdict[str, int] = defaultdict(int)
        resource_movements: dict[tuple[str, int, str, str], FatoMovement] = {}
        legacy_movements: dict[tuple[str, int, str, str], FatoMovement] = {}
        waiting_since: dict[str, float] = {}
        wait_times: list[dict[str, Any]] = []
        completed_uam: set[str] = set()
        uam_users: set[str] = set()
        eligible_fallback: set[str] = set()
        onboard: defaultdict[str, set[str]] = defaultdict(set)
        occupancy_events: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        walk_legs: list[WalkLeg] = []
        active_walk: dict[str, tuple[float, str, int]] = {}
        walk_session: defaultdict[str, int] = defaultdict(int)
        origin_departure: dict[str, float] = {}
        final_arrival: dict[str, float] = {}
        background_departure: dict[str, float] = {}
        background_arrival: dict[str, float] = {}
        event_count = 0
        start_time = math.inf
        end_time = 0.0

        def set_onboard(
            vehicle: str, person: str, present: bool, time_value: float
        ) -> None:
            if not vehicle or not person:
                return
            passengers = onboard[vehicle]
            changed = False
            if present and person not in passengers:
                passengers.add(person)
                changed = True
            elif not present and person in passengers:
                passengers.remove(person)
                changed = True
            if changed:
                occupancy_events[vehicle].append(
                    {
                        "time": round(time_value, 3),
                        "count": len(passengers),
                        "passengerIds": sorted(passengers),
                    }
                )

        def close_active(vehicle_id: str, time_value: float) -> None:
            active = active_link.pop(vehicle_id, None)
            if not active:
                return
            link_id, entered_at, session_id, mode = active
            if time_value < entered_at:
                return
            segments.append(
                LinkSegment(
                    vehicle_id=vehicle_id,
                    session_id=session_id,
                    link_id=link_id,
                    start_time=entered_at,
                    end_time=time_value,
                    mode=mode,
                )
            )
            used_links.add(link_id)

        for element in _iter_elements(self.paths.events, "event"):
            attributes = element.attrib
            event_type = attributes.get("type", "")
            time_value = _as_float(attributes.get("time"))
            event_count += 1
            event_types[event_type] += 1
            start_time = min(start_time, time_value)
            end_time = max(end_time, time_value)

            person_id = attributes.get("person", "")
            vehicle_id = attributes.get("vehicle", "") or attributes.get(
                "vehicleId", ""
            )
            link_id = attributes.get("link", "")
            normalized_event_type = re.sub(r"[^a-z]", "", event_type.lower())

            if person_id.startswith("Pax_"):
                eligible_fallback.add(person_id)
            if self.paths.background_traffic_enabled and vehicle_id and (
                person_id in background_people
                or vehicle_id in background_people
                or vehicle_id.startswith("background_car_")
            ):
                background_vehicles.add(vehicle_id)

            if normalized_event_type == "transitdriverstarts" and vehicle_id:
                transit_vehicles.add(vehicle_id)
                vehicle_mode[vehicle_id] = _scheduled_vehicle_mode(attributes)
                driver_id = attributes.get("driverId", "")
                if driver_id:
                    transit_drivers.add(driver_id)
                    set_onboard(vehicle_id, driver_id, False, time_value)

            if event_type == "vehicle enters traffic" and vehicle_id:
                current_session[vehicle_id] += 1
                mode = _vehicle_travel_mode(
                    vehicle_id,
                    attributes.get("networkMode"),
                    transit_vehicles,
                )
                vehicle_mode[vehicle_id] = mode
                if mode == "car" and person_id:
                    set_onboard(vehicle_id, person_id, True, time_value)
                if link_id:
                    active_link[vehicle_id] = (
                        link_id,
                        time_value,
                        current_session[vehicle_id],
                        mode,
                    )
                    used_links.add(link_id)
                if mode == "uam" and onboard[vehicle_id]:
                    stage_deltas.append(
                        (time_value, "boardingHold", -len(onboard[vehicle_id]))
                    )

            elif event_type == "entered link" and vehicle_id and link_id:
                close_active(vehicle_id, time_value)
                mode = vehicle_mode.get(
                    vehicle_id,
                    _vehicle_travel_mode(vehicle_id, None, transit_vehicles),
                )
                if not current_session[vehicle_id]:
                    current_session[vehicle_id] = 1
                active_link[vehicle_id] = (
                    link_id,
                    time_value,
                    current_session[vehicle_id],
                    mode,
                )
                used_links.add(link_id)
                fato_entry = re.match(
                    r"link_(apron_fato|fato_landing)_(\d+)_(.+)$", link_id
                )
                if fato_entry and vehicle_id not in fato_active:
                    direction = (
                        "takeoff" if fato_entry.group(1) == "apron_fato" else "landing"
                    )
                    fato_passage[vehicle_id] += 1
                    fato_active[vehicle_id] = (
                        fato_entry.group(2),
                        fato_entry.group(3),
                        direction,
                        fato_passage[vehicle_id],
                    )
                    stage_deltas.append((time_value, "fatoOccupancy", 1))
                    fato_stage_deltas_by_vertiport[fato_entry.group(2)].append(
                        (time_value, "fatoOccupancy", 1)
                    )

            elif event_type == "left link" and vehicle_id:
                close_active(vehicle_id, time_value)
                resource_match = re.match(
                    r"link_fato_resource_(\d+)_(.+)$", link_id
                )
                if resource_match:
                    vertiport_id, fato_id = resource_match.groups()
                    active_fato = fato_active.get(vehicle_id)
                    movement_type = (
                        active_fato[2]
                        if active_fato
                        and active_fato[0] == vertiport_id
                        and active_fato[1] == fato_id
                        else "unknown"
                    )
                    movement_key = (
                        vehicle_id,
                        active_fato[3] if active_fato else fato_passage[vehicle_id],
                        vertiport_id,
                        fato_id,
                    )
                    resource_movements[movement_key] = FatoMovement(
                        time=time_value,
                        vertiport_id=vertiport_id,
                        fato_id=fato_id,
                        vehicle_id=vehicle_id,
                        movement_type=movement_type,
                    )

                fato_exit = re.match(
                    r"link_fato_(takeoff|apron)_(\d+)_(.+)$", link_id
                )
                if fato_exit and vehicle_id in fato_active:
                    movement_type, vertiport_id, fato_id = fato_exit.groups()
                    if movement_type == "apron":
                        movement_type = "landing"
                    movement_key = (
                        vehicle_id,
                        fato_active[vehicle_id][3],
                        vertiport_id,
                        fato_id,
                    )
                    # Compatibility with event files produced before the
                    # shared resource link was introduced.  When a resource
                    # event exists for the same FATO passage it takes
                    # precedence below, preventing double counting.
                    legacy_movements[movement_key] = FatoMovement(
                        time=time_value,
                        vertiport_id=vertiport_id,
                        fato_id=fato_id,
                        vehicle_id=vehicle_id,
                        movement_type=movement_type,
                    )
                    fato_active.pop(vehicle_id, None)
                    stage_deltas.append((time_value, "fatoOccupancy", -1))
                    fato_stage_deltas_by_vertiport[vertiport_id].append(
                        (time_value, "fatoOccupancy", -1)
                    )

            elif event_type == "vehicle leaves traffic" and vehicle_id:
                close_active(vehicle_id, time_value)
                if vehicle_mode.get(vehicle_id) == "car" and person_id:
                    set_onboard(vehicle_id, person_id, False, time_value)

            if normalized_event_type == "personentersvehicle":
                if (
                    vehicle_id
                    and person_id
                    and person_id != vehicle_id
                    and person_id not in transit_drivers
                    and not person_id.startswith("pt_")
                ):
                    set_onboard(vehicle_id, person_id, True, time_value)
            elif normalized_event_type == "personleavesvehicle":
                if vehicle_id and person_id:
                    set_onboard(vehicle_id, person_id, False, time_value)

            if event_type == "actstart":
                activity_type = attributes.get("actType")
                if activity_type == "vertiport_entry":
                    stage_deltas.append((time_value, "terminalProcessing", 1))
                elif activity_type == "vertiport_boarding":
                    stage_deltas.append((time_value, "terminalProcessing", -1))

            elif event_type == "passenger waiting" and person_id:
                waiting_since[person_id] = time_value
                uam_users.add(person_id)
                stage_deltas.append((time_value, "uamDispatch", 1))

            elif event_type == "passenger picked up" and person_id:
                started = waiting_since.pop(person_id, time_value)
                wait_times.append(
                    {
                        "personId": person_id,
                        "urgency": urgency.get(person_id, "unclassified"),
                        "waitSeconds": max(0.0, time_value - started),
                        "completed": True,
                    }
                )
                stage_deltas.append((time_value, "uamDispatch", -1))
                stage_deltas.append((time_value, "boardingHold", 1))
                if vehicle_id:
                    set_onboard(vehicle_id, person_id, True, time_value)

            elif event_type == "passenger dropped off" and person_id:
                completed_uam.add(person_id)
                if vehicle_id:
                    set_onboard(vehicle_id, person_id, False, time_value)

            leg_mode = (
                attributes.get("legMode")
                or attributes.get("routingMode")
                or attributes.get("mode")
            )
            if event_type == "departure" and person_id and _is_walk_mode(leg_mode):
                walk_session[person_id] += 1
                active_walk[person_id] = (
                    time_value,
                    link_id,
                    walk_session[person_id],
                )
                if link_id:
                    used_links.add(link_id)
            elif event_type == "arrival" and person_id and _is_walk_mode(leg_mode):
                active = active_walk.pop(person_id, None)
                if active:
                    started_at, start_link_id, session_id = active
                    if time_value >= started_at and start_link_id and link_id:
                        walk_legs.append(
                            WalkLeg(
                                person_id=person_id,
                                session_id=session_id,
                                start_link_id=start_link_id,
                                end_link_id=link_id,
                                start_time=started_at,
                                end_time=time_value,
                            )
                        )
                        used_links.update((start_link_id, link_id))

            is_tracked_person = person_id in uam_eligible or person_id.startswith(
                "Pax_"
            )
            if event_type == "departure" and is_tracked_person:
                origin_departure.setdefault(person_id, time_value)
                if leg_mode:
                    observed_leg_modes[person_id].add(leg_mode)
            elif event_type == "arrival" and is_tracked_person:
                final_arrival[person_id] = time_value

            if event_type == "departure" and person_id in background_people:
                background_departure.setdefault(person_id, time_value)
            elif event_type == "arrival" and person_id in background_people:
                background_arrival[person_id] = time_value

        for vehicle_id in list(active_link):
            close_active(vehicle_id, end_time)

        for person_id, started in waiting_since.items():
            wait_times.append(
                {
                    "personId": person_id,
                    "urgency": urgency.get(person_id, "unclassified"),
                    "waitSeconds": max(0.0, end_time - started),
                    "completed": False,
                }
            )

        fato_movements_by_passage = dict(legacy_movements)
        fato_movements_by_passage.update(resource_movements)
        fato_movements = sorted(
            fato_movements_by_passage.values(),
            key=lambda movement: (
                movement.time,
                movement.vertiport_id,
                movement.fato_id,
                movement.vehicle_id,
            ),
        )

        eligible = uam_eligible or eligible_fallback
        journeys = []
        for person_id in sorted(eligible):
            departure = origin_departure.get(person_id)
            arrival = final_arrival.get(person_id)
            journeys.append(
                {
                    "personId": person_id,
                    "urgency": urgency.get(person_id, "unclassified"),
                    "outcome": _journey_outcome(
                        observed_leg_modes[person_id],
                        person_id in completed_uam,
                    ),
                    "departureTime": departure,
                    "arrivalTime": arrival,
                    "travelTimeSeconds": (
                        max(0.0, arrival - departure)
                        if departure is not None and arrival is not None
                        else None
                    ),
                }
            )

        departure_times = [
            *origin_departure.values(),
            *background_departure.values(),
        ]
        arrival_times = [
            *final_arrival.values(),
            *background_arrival.values(),
        ]
        observed_start = min(departure_times) if departure_times else start_time
        observed_end = max(arrival_times) if arrival_times else end_time

        return {
            "event_count": event_count,
            "event_types": event_types,
            "segments": segments,
            "occupancy_events": occupancy_events,
            "background_vehicles": background_vehicles,
            "walk_legs": walk_legs,
            "used_links": used_links,
            "stage_deltas": stage_deltas,
            "fato_stage_deltas_by_vertiport": fato_stage_deltas_by_vertiport,
            "fato_movements": fato_movements,
            "wait_times": wait_times,
            "journeys": journeys,
            "completed_uam": completed_uam,
            "observed_leg_modes": observed_leg_modes,
            "uam_users": uam_users,
            "eligible_fallback": eligible_fallback,
            "start_time": 0.0 if math.isinf(observed_start) else observed_start,
            "end_time": observed_end,
        }

    def _read_network(
        self, used_links: set[str]
    ) -> tuple[dict[str, LinkRecord], dict[str, tuple[float, float]]]:
        selected_links: dict[str, LinkRecord] = {}
        needed_nodes: set[str] = set()

        for element in _iter_elements(self.paths.network, "link"):
            attributes = element.attrib
            link_id = attributes.get("id", "")
            modes = attributes.get("modes", "")
            if (
                link_id not in used_links
                and not link_id.startswith(CUSTOM_LINK_PREFIXES)
                and not _allows_surface_walk_route(modes)
            ):
                continue
            record = LinkRecord(
                link_id=link_id,
                from_node=attributes.get("from", ""),
                to_node=attributes.get("to", ""),
                length=_as_float(attributes.get("length")),
                freespeed=_as_float(attributes.get("freespeed")),
                capacity=_as_float(attributes.get("capacity")),
                modes=modes,
            )
            selected_links[link_id] = record
            needed_nodes.update((record.from_node, record.to_node))

        nodes: dict[str, tuple[float, float]] = {}
        for element in _iter_elements(self.paths.network, "node"):
            node_id = element.attrib.get("id", "")
            if node_id in needed_nodes:
                nodes[node_id] = (
                    _as_float(element.attrib.get("x")),
                    _as_float(element.attrib.get("y")),
                )

        missing_links = used_links - selected_links.keys()
        if missing_links:
            self.warnings.append(
                f"{len(missing_links)} traversed links were not found in the network."
            )
        return selected_links, nodes

    def _coordinate_transformer(self):
        try:
            from pyproj import Transformer
        except ImportError as exc:
            raise RuntimeError(
                "Module 5 requires pyproj to transform MATSim coordinates. "
                "Install module5/requirements.txt."
            ) from exc
        return Transformer.from_crs(self.crs, "EPSG:4326", always_xy=True)

    def _build_trajectories(
        self,
        segments: list[LinkSegment],
        occupancy_events: dict[str, list[dict[str, Any]]],
        background_vehicles: set[str],
        links: dict[str, LinkRecord],
        nodes: dict[str, tuple[float, float]],
        transformer: Any,
    ) -> list[dict[str, Any]]:
        by_session: defaultdict[tuple[str, int], list[LinkSegment]] = defaultdict(list)
        for segment in segments:
            by_session[(segment.vehicle_id, segment.session_id)].append(segment)

        trajectories: list[dict[str, Any]] = []
        for (vehicle_id, session_id), session_segments in sorted(by_session.items()):
            session_segments.sort(key=lambda item: (item.start_time, item.end_time))
            coordinates_xy: list[tuple[float, float]] = []
            timestamps: list[float] = []
            link_ids: list[str] = []

            for segment in session_segments:
                link = links.get(segment.link_id)
                if not link:
                    continue
                start = nodes.get(link.from_node)
                end = nodes.get(link.to_node)
                if start is None or end is None:
                    continue
                if not coordinates_xy or coordinates_xy[-1] != start:
                    coordinates_xy.append(start)
                    timestamps.append(segment.start_time)
                coordinates_xy.append(end)
                timestamps.append(max(segment.start_time, segment.end_time))
                link_ids.append(segment.link_id)

            if len(coordinates_xy) < 2:
                continue

            tolerance = 8.0 if session_segments[0].mode != "uam" else 1.0
            selected = _rdp_indices(coordinates_xy, tolerance)
            selected = _bounded_indices(selected, 900)
            simplified_xy = [coordinates_xy[index] for index in selected]
            simplified_times = [timestamps[index] for index in selected]
            path = [
                [round(lon, 7), round(lat, 7)]
                for lon, lat in (
                    transformer.transform(point[0], point[1])
                    for point in simplified_xy
                )
            ]
            mode = session_segments[0].mode
            occupancy = []
            current_occupancy = {"count": 0, "passengerIds": []}
            for sample in occupancy_events.get(vehicle_id, []):
                if sample["time"] <= simplified_times[0] + 1e-9:
                    current_occupancy = {
                        "count": sample["count"],
                        "passengerIds": sample["passengerIds"],
                    }
                elif sample["time"] <= simplified_times[-1] + 1e-9:
                    occupancy.append(sample)
            occupancy.insert(
                0,
                {
                    "time": round(simplified_times[0], 3),
                    "count": current_occupancy["count"],
                    "passengerIds": current_occupancy["passengerIds"],
                },
            )
            trajectories.append(
                {
                    "id": f"{vehicle_id}:{session_id}",
                    "vehicleId": vehicle_id,
                    "mode": mode,
                    "isBackground": vehicle_id in background_vehicles,
                    "startTime": simplified_times[0],
                    "endTime": simplified_times[-1],
                    "path": path,
                    "timestamps": [round(value, 3) for value in simplified_times],
                    "linkCount": len(link_ids),
                    "occupancy": occupancy,
                }
            )
        return trajectories

    def _build_walk_trajectories(
        self,
        walk_legs: list[WalkLeg],
        background_people: set[str],
        links: dict[str, LinkRecord],
        nodes: dict[str, tuple[float, float]],
        transformer: Any,
    ) -> list[dict[str, Any]]:
        """Route observed walk legs over the network's walk-enabled links."""

        def link_midpoint(link_id: str) -> tuple[float, float] | None:
            link = links.get(link_id)
            if not link:
                return None
            start = nodes.get(link.from_node)
            end = nodes.get(link.to_node)
            if start is None or end is None:
                return None
            return ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)

        adjacency: defaultdict[str, list[tuple[str, float]]] = defaultdict(list)
        walk_node_ids: set[str] = set()
        for link in links.values():
            if _allows_surface_walk_route(link.modes) and link.from_node and link.to_node:
                route_cost = max(link.length, 0.001) * (
                    1.0 if _allows_walk(link.modes) else 4.0
                )
                adjacency[link.from_node].append(
                    (link.to_node, route_cost)
                )
                adjacency[link.to_node].append(
                    (link.from_node, route_cost)
                )
                walk_node_ids.update((link.from_node, link.to_node))

        walk_nodes = [
            (node_id, nodes[node_id])
            for node_id in walk_node_ids
            if node_id in nodes
        ]
        nearest_walk_nodes_cache: dict[str, list[tuple[str, float]]] = {}

        def nearest_walk_nodes(
            link_id: str, point: tuple[float, float]
        ) -> list[tuple[str, float]]:
            if link_id in nearest_walk_nodes_cache:
                return nearest_walk_nodes_cache[link_id]
            nearest = heapq.nsmallest(
                16,
                walk_nodes,
                key=lambda item: (
                    (item[1][0] - point[0]) ** 2 + (item[1][1] - point[1]) ** 2
                ),
            )
            candidates = [
                (
                    node_id,
                    math.hypot(
                        coordinate[0] - point[0], coordinate[1] - point[1]
                    ),
                )
                for node_id, coordinate in nearest
            ]
            nearest_walk_nodes_cache[link_id] = candidates
            return candidates

        def endpoint_candidates(
            link: LinkRecord, midpoint: tuple[float, float]
        ) -> list[tuple[str, float]]:
            if _allows_surface_walk_route(link.modes):
                cost = max(link.length, 0.0) / 2 * (
                    1.0 if _allows_walk(link.modes) else 4.0
                )
                return [
                    (node_id, cost)
                    for node_id in (link.from_node, link.to_node)
                    if node_id and node_id in walk_node_ids and node_id in nodes
                ]
            return nearest_walk_nodes(link.link_id, midpoint)

        route_cache: dict[
            tuple[str, str], tuple[list[tuple[float, float]], int] | None
        ] = {}

        def shortest_route(
            start_link_id: str, end_link_id: str
        ) -> tuple[list[tuple[float, float]], int] | None:
            cache_key = (start_link_id, end_link_id)
            if cache_key in route_cache:
                return route_cache[cache_key]

            start_link = links.get(start_link_id)
            end_link = links.get(end_link_id)
            start_midpoint = link_midpoint(start_link_id)
            end_midpoint = link_midpoint(end_link_id)
            if not start_link or not end_link or not start_midpoint or not end_midpoint:
                route_cache[cache_key] = None
                return None
            if start_link_id == end_link_id:
                result = ([start_midpoint, end_midpoint], 1)
                route_cache[cache_key] = result
                return result

            distances: dict[str, float] = {}
            previous: dict[str, str] = {}
            frontier: list[tuple[float, str]] = []
            for node_id, start_cost in endpoint_candidates(start_link, start_midpoint):
                if start_cost < distances.get(node_id, math.inf):
                    distances[node_id] = start_cost
                    heapq.heappush(frontier, (start_cost, node_id))

            targets = dict(endpoint_candidates(end_link, end_midpoint))
            reached: str | None = None
            best_total = math.inf
            while frontier:
                distance, node_id = heapq.heappop(frontier)
                if distance != distances.get(node_id):
                    continue
                if distance >= best_total:
                    break
                if node_id in targets:
                    total = distance + targets[node_id]
                    if total < best_total:
                        reached = node_id
                        best_total = total
                for next_node, link_cost in adjacency.get(node_id, []):
                    candidate = distance + link_cost
                    if candidate < distances.get(next_node, math.inf):
                        distances[next_node] = candidate
                        previous[next_node] = node_id
                        heapq.heappush(frontier, (candidate, next_node))

            if reached is None:
                route_cache[cache_key] = None
                return None

            route_nodes = [reached]
            while route_nodes[-1] in previous:
                route_nodes.append(previous[route_nodes[-1]])
            route_nodes.reverse()
            points = [start_midpoint]
            points.extend(nodes[node_id] for node_id in route_nodes)
            points.append(end_midpoint)
            deduplicated = [points[0]]
            for point in points[1:]:
                if point != deduplicated[-1]:
                    deduplicated.append(point)
            if len(deduplicated) == 1:
                deduplicated.append(deduplicated[0])
            result = (deduplicated, max(1, len(route_nodes) + 1))
            route_cache[cache_key] = result
            return result

        trajectories: list[dict[str, Any]] = []
        unroutable = 0
        for leg in walk_legs:
            routed = shortest_route(leg.start_link_id, leg.end_link_id)
            if routed is None:
                unroutable += 1
                continue
            route_xy, link_count = routed
            segment_lengths = [
                math.hypot(end[0] - start[0], end[1] - start[1])
                for start, end in zip(route_xy, route_xy[1:])
            ]
            total_length = sum(segment_lengths)
            duration = max(0.0, leg.end_time - leg.start_time)
            cumulative = 0.0
            timestamps = [leg.start_time]
            for length in segment_lengths:
                cumulative += length
                fraction = cumulative / total_length if total_length else 1.0
                timestamps.append(leg.start_time + duration * fraction)
            geographic = [
                [round(lon, 7), round(lat, 7)]
                for lon, lat in (
                    transformer.transform(point[0], point[1])
                    for point in route_xy
                )
            ]
            trajectories.append(
                {
                    "id": f"walk:{leg.person_id}:{leg.session_id}",
                    "vehicleId": leg.person_id,
                    "mode": "walk",
                    "isBackground": leg.person_id in background_people,
                    "startTime": round(leg.start_time, 3),
                    "endTime": round(leg.end_time, 3),
                    "path": geographic,
                    "timestamps": [round(value, 3) for value in timestamps],
                    "linkCount": link_count,
                    "occupancy": [
                        {
                            "time": round(leg.start_time, 3),
                            "count": 0,
                            "passengerIds": [],
                        }
                    ],
                }
            )
        if unroutable:
            self.warnings.append(
                f"{unroutable} observed walk legs could not be routed over walk-enabled links."
            )
        return trajectories

    def _build_queue_series(
        self,
        stage_deltas: list[tuple[float, str, int]],
        start_time: float,
        end_time: float,
    ) -> list[dict[str, Any]]:
        stage_keys = (
            "terminalProcessing",
            "uamDispatch",
            "boardingHold",
            "fatoOccupancy",
        )
        state = {key: 0 for key in stage_keys}
        deltas = sorted(stage_deltas, key=lambda item: (item[0], item[1]))
        index = 0
        first = math.floor(start_time / self.queue_interval_seconds)
        last = math.ceil(end_time / self.queue_interval_seconds)
        series = []
        for slot in range(first, last + 1):
            time_value = float(slot * self.queue_interval_seconds)
            while index < len(deltas) and deltas[index][0] <= time_value:
                _, key, delta = deltas[index]
                state[key] = max(0, state[key] + delta)
                index += 1
            series.append(
                {
                    "time": time_value,
                    **{key: state[key] for key in stage_keys},
                }
            )
        return series

    @staticmethod
    def _build_fato_occupancy_series(
        stage_deltas: list[tuple[float, str, int]],
        start_time: float,
        end_time: float,
    ) -> list[dict[str, Any]]:
        """Preserve every FATO entry/exit instead of sampling short occupancies."""

        occupancy = 0
        deltas_by_time: defaultdict[float, int] = defaultdict(int)
        for time_value, stage, delta in stage_deltas:
            if stage == "fatoOccupancy":
                deltas_by_time[time_value] += delta

        for time_value in sorted(deltas_by_time):
            if time_value >= start_time:
                break
            occupancy = max(0, occupancy + deltas_by_time[time_value])

        series = [{"time": start_time, "occupancy": occupancy}]
        for time_value in sorted(deltas_by_time):
            if time_value < start_time or time_value > end_time:
                continue
            occupancy = max(0, occupancy + deltas_by_time[time_value])
            if time_value == series[-1]["time"]:
                series[-1]["occupancy"] = occupancy
            else:
                series.append({"time": time_value, "occupancy": occupancy})
        if end_time != series[-1]["time"]:
            series.append({"time": end_time, "occupancy": occupancy})
        return series

    def _build_capacity(
        self,
        movements: list[FatoMovement],
        start_time: float,
        end_time: float,
    ) -> dict[str, Any]:
        design = json.loads(self.paths.design_report.read_text(encoding="utf-8"))
        config = _runtime_config()
        configured_names = {
            str(item["id"]): item.get("name", f"Vertiport {item['id']}")
            for item in getattr(config, "VERTIPORTS", [])
        } if config is not None else {}
        design_vertiports = {
            str(item["id"]): item for item in design.get("vertiports", [])
        }
        capacities = {
            vertiport_id: _as_float(
                str(item.get("aggregate_fato_capacity_veh_h", 0))
            )
            for vertiport_id, item in design_vertiports.items()
        }
        separation_requirements: dict[str, float] = {}
        configured_fatos: set[tuple[str, str]] = set()
        for vertiport_id, item in design_vertiports.items():
            fato_count = max(0, int(_as_float(str(item.get("fato_count", 0)))))
            requirement = _as_float(str(item.get("t_sep_s", 0)))
            if requirement <= 0.0 and capacities[vertiport_id] > 0.0 and fato_count:
                requirement = fato_count * 3600.0 / capacities[vertiport_id]
            separation_requirements[vertiport_id] = requirement
            fato_ids = [
                str(fato.get("id", ""))
                for fato in item.get("fatos", [])
                if str(fato.get("id", ""))
            ]
            if not fato_ids and fato_count:
                fato_ids = [f"F{index}" for index in range(1, fato_count + 1)]
            configured_fatos.update(
                (vertiport_id, fato_id) for fato_id in fato_ids
            )

        movement_times: defaultdict[str, list[float]] = defaultdict(list)
        movements_by_fato: defaultdict[
            tuple[str, str], list[FatoMovement]
        ] = defaultdict(list)
        for movement in movements:
            movement_times[movement.vertiport_id].append(movement.time)
            movements_by_fato[
                (movement.vertiport_id, movement.fato_id)
            ].append(movement)
        for times in movement_times.values():
            times.sort()
        for fato_movements in movements_by_fato.values():
            fato_movements.sort(key=lambda movement: movement.time)

        series: list[dict[str, Any]] = []
        breaches = 0
        per_vertiport_series: dict[str, list[dict[str, Any]]] = {
            vertiport_id: [] for vertiport_id in capacities
        }
        first = math.floor(start_time / self.queue_interval_seconds)
        last = math.ceil(end_time / self.queue_interval_seconds)
        for slot in range(first, last + 1):
            time_value = float(slot * self.queue_interval_seconds)
            combined_movements = 0
            total_capacity = 0.0
            peak_utilisation = 0.0
            any_breach = False
            for vertiport_id, capacity in capacities.items():
                times = movement_times[vertiport_id]
                left = bisect.bisect_right(times, time_value - 3600.0)
                right = bisect.bisect_right(times, time_value)
                rolling = right - left
                utilisation = _safe_ratio(rolling, capacity)
                breach = bool(capacity and rolling > capacity)
                per_vertiport_series[vertiport_id].append(
                    {
                        "time": time_value,
                        "movementsLastHour": rolling,
                        "capacityVehPerHour": capacity,
                        "utilisation": round(utilisation, 4),
                        "breach": breach,
                    }
                )
                combined_movements += rolling
                total_capacity += capacity
                peak_utilisation = max(peak_utilisation, utilisation)
                any_breach = any_breach or breach
            breaches += int(any_breach)
            series.append(
                {
                    "time": time_value,
                    "movementsLastHour": combined_movements,
                    "capacityVehPerHour": total_capacity,
                    "utilisation": round(peak_utilisation, 4),
                    "breach": any_breach,
                }
            )
        headway_series: list[dict[str, Any]] = []
        by_fato = []
        headway_comparisons = 0
        headway_violations = 0
        minimum_separation: float | None = None
        all_fatos = configured_fatos | set(movements_by_fato)
        for vertiport_id, fato_id in sorted(all_fatos):
            fato_movements = movements_by_fato[(vertiport_id, fato_id)]
            requirement = separation_requirements.get(vertiport_id, 0.0)
            comparison_count = 0
            violation_count = 0
            fato_minimum: float | None = None
            for previous, current in zip(fato_movements, fato_movements[1:]):
                separation = max(0.0, current.time - previous.time)
                compliant = not requirement or separation + 1e-9 >= requirement
                if requirement:
                    comparison_count += 1
                    violation_count += int(not compliant)
                fato_minimum = (
                    separation
                    if fato_minimum is None
                    else min(fato_minimum, separation)
                )
                minimum_separation = (
                    separation
                    if minimum_separation is None
                    else min(minimum_separation, separation)
                )
                headway_series.append(
                    {
                        "time": round(current.time, 3),
                        "previousMovementTime": round(previous.time, 3),
                        "vertiportId": vertiport_id,
                        "fatoId": fato_id,
                        "name": (
                            f"{configured_names.get(vertiport_id, f'Vertiport {vertiport_id}')} "
                            f"FATO {fato_id}"
                        ),
                        "separationSeconds": round(separation, 3),
                        "requiredSeparationSeconds": requirement,
                        "compliant": compliant,
                        "vehicleId": current.vehicle_id,
                        "movementType": current.movement_type,
                    }
                )
            headway_comparisons += comparison_count
            headway_violations += violation_count
            by_fato.append(
                {
                    "vertiportId": vertiport_id,
                    "fatoId": fato_id,
                    "name": (
                        f"{configured_names.get(vertiport_id, f'Vertiport {vertiport_id}')} "
                        f"FATO {fato_id}"
                    ),
                    "tSepSeconds": requirement,
                    "fatoCapacityVehPerHour": _safe_ratio(3600.0, requirement),
                    "movementCount": len(fato_movements),
                    "headwayComparisonCount": comparison_count,
                    "headwayViolationCount": violation_count,
                    "headwayViolationProportion": round(
                        _safe_ratio(violation_count, comparison_count), 4
                    ),
                    "minimumObservedSeparationSeconds": (
                        round(fato_minimum, 3) if fato_minimum is not None else None
                    ),
                }
            )

        by_vertiport = []
        for vertiport_id, capacity in capacities.items():
            samples = per_vertiport_series[vertiport_id]
            facility_breaches = sum(int(sample["breach"]) for sample in samples)
            fato_summaries = [
                summary
                for summary in by_fato
                if summary["vertiportId"] == vertiport_id
            ]
            facility_comparisons = sum(
                summary["headwayComparisonCount"] for summary in fato_summaries
            )
            facility_headway_violations = sum(
                summary["headwayViolationCount"] for summary in fato_summaries
            )
            facility_minimums = [
                summary["minimumObservedSeparationSeconds"]
                for summary in fato_summaries
                if summary["minimumObservedSeparationSeconds"] is not None
            ]
            by_vertiport.append(
                {
                    "vertiportId": vertiport_id,
                    "name": configured_names.get(
                        vertiport_id, f"Vertiport {vertiport_id}"
                    ),
                    "fatoCapacityVehPerHour": capacity,
                    "movementCount": len(movement_times[vertiport_id]),
                    "breachProportion": round(
                        _safe_ratio(facility_breaches, len(samples)), 4
                    ),
                    "tSepSeconds": separation_requirements.get(vertiport_id, 0.0),
                    "headwayComparisonCount": facility_comparisons,
                    "headwayViolationCount": facility_headway_violations,
                    "headwayViolationProportion": round(
                        _safe_ratio(
                            facility_headway_violations, facility_comparisons
                        ),
                        4,
                    ),
                    "minimumObservedSeparationSeconds": (
                        min(facility_minimums) if facility_minimums else None
                    ),
                    "series": samples,
                }
            )
        if headway_violations:
            self.warnings.append(
                f"{headway_violations} of {headway_comparisons} consecutive "
                "FATO movement intervals violated the configured separation time."
            )
        return {
            "definition": (
                "Share of observed time where at least one vertiport's rolling "
                "one-hour FATO movements exceed that vertiport's configured "
                "aggregate FATO design capacity."
            ),
            "fatoCapacityVehPerHour": sum(capacities.values()),
            "movementCount": len(movements),
            "breachProportion": round(_safe_ratio(breaches, len(series)), 4),
            "series": series,
            "byVertiport": by_vertiport,
            "headwayDefinition": (
                "A headway violation occurs when consecutive movements on the "
                "same physical FATO are separated by less than its configured "
                "t_sep value. This check is independent of rolling-hour capacity."
            ),
            "headwayComparisonCount": headway_comparisons,
            "headwayViolationCount": headway_violations,
            "headwayViolationProportion": round(
                _safe_ratio(headway_violations, headway_comparisons), 4
            ),
            "minimumObservedSeparationSeconds": (
                round(minimum_separation, 3)
                if minimum_separation is not None
                else None
            ),
            "headwaySeries": sorted(
                headway_series,
                key=lambda sample: (
                    sample["time"], sample["vertiportId"], sample["fatoId"]
                ),
            ),
            "byFato": by_fato,
        }

    def _build_outcomes(
        self,
        *,
        event_data: dict[str, Any],
        urgency: dict[str, str],
        uam_eligible: set[str],
    ) -> dict[str, Any]:
        eligible = uam_eligible or event_data["eligible_fallback"]
        completed = event_data["completed_uam"]
        observed_leg_modes = event_data["observed_leg_modes"]
        categories = sorted({urgency.get(person, "unclassified") for person in eligible})
        by_urgency = []
        for category in categories:
            people = {person for person in eligible if urgency.get(person, "unclassified") == category}
            completed_count = len(people & completed)
            journey_outcomes = Counter(
                _journey_outcome(observed_leg_modes[person], person in completed)
                for person in people
            )
            non_uam = len(people) - completed_count
            by_urgency.append(
                {
                    "urgency": category,
                    "eligible": len(people),
                    "uamCompleted": completed_count,
                    "carSelected": journey_outcomes["car"],
                    "ptSelected": journey_outcomes["pt"],
                    "unobserved": journey_outcomes["unobserved"],
                    "abandonmentRate": round(_safe_ratio(non_uam, len(people)), 4),
                }
            )
        total = len(eligible)
        completed_count = len(eligible & completed)
        journey_outcomes = Counter(
            _journey_outcome(observed_leg_modes[person], person in completed)
            for person in eligible
        )
        non_uam = total - completed_count
        return {
            "definition": (
                "Outcomes use executed MATSim events: a UAM passenger drop-off "
                "takes precedence, otherwise PT or car is identified from observed "
                "leg modes. Travellers without a recognised executed mode are "
                "reported as unobserved."
            ),
            "eligibleTravellers": total,
            "uamCompleted": completed_count,
            "carSelected": journey_outcomes["car"],
            "ptSelected": journey_outcomes["pt"],
            "unobserved": journey_outcomes["unobserved"],
            "abandonmentRate": round(_safe_ratio(non_uam, total), 4),
            "byUrgency": by_urgency,
        }

    def _build_landmarks(self, transformer: Any) -> list[dict[str, Any]]:
        config = _runtime_config()
        landmarks: list[dict[str, Any]] = []
        if config is not None:
            demand_events = getattr(config, "DEMAND_EVENTS", [])
            for index, event in enumerate(demand_events, start=1):
                lon, lat = transformer.transform(
                    float(event["origin_x"]), float(event["origin_y"])
                )
                landmarks.append(
                    {
                        "id": f"demand-origin-{index}",
                        "label": event.get("source_name", f"Demand origin {index}"),
                        "kind": "origin",
                        "position": [round(lon, 7), round(lat, 7)],
                    }
                )
            for vertiport in getattr(config, "VERTIPORTS", []):
                lon, lat = transformer.transform(
                    float(vertiport["x"]), float(vertiport["y"])
                )
                landmarks.append(
                    {
                        "id": f"vertiport-{vertiport['id']}",
                        "label": vertiport.get("name", f"Vertiport {vertiport['id']}"),
                        "kind": "vertiport",
                        "position": [round(lon, 7), round(lat, 7)],
                    }
                )
        return landmarks

    def _build_vertiports(
        self,
        links: dict[str, LinkRecord],
        nodes: dict[str, tuple[float, float]],
        transformer: Any,
    ) -> list[dict[str, Any]]:
        design = json.loads(self.paths.design_report.read_text(encoding="utf-8"))
        config = _runtime_config()
        configured_names = {
            str(item["id"]): item.get("name", f"Vertiport {item['id']}")
            for item in getattr(config, "VERTIPORTS", [])
        } if config is not None else {}

        results = []
        for item in design.get("vertiports", []):
            vertiport_id = str(item["id"])
            selected_nodes = {
                node_id: position
                for node_id, position in nodes.items()
                if self._node_belongs_to_vertiport(node_id, vertiport_id)
            }
            selected_links = [
                link
                for link in links.values()
                if link.from_node in selected_nodes and link.to_node in selected_nodes
            ]

            origin = selected_nodes.get(f"vt_terminal_{vertiport_id}")
            if origin is None:
                candidates = list(selected_nodes.values())
                origin = candidates[0] if candidates else (0.0, 0.0)

            def local(position: tuple[float, float]) -> list[float]:
                return [
                    round(position[0] - origin[0], 3),
                    round(position[1] - origin[1], 3),
                ]

            graph_nodes = []
            for node_id, position in selected_nodes.items():
                kind = self._node_kind(node_id)
                lon, lat = transformer.transform(position[0], position[1])
                graph_nodes.append(
                    {
                        "id": node_id,
                        "label": self._node_label(node_id),
                        "kind": kind,
                        "position": local(position),
                        "geographicPosition": [round(lon, 7), round(lat, 7)],
                    }
                )

            graph_links = [
                {
                    "id": link.link_id,
                    "source": link.from_node,
                    "target": link.to_node,
                    "capacity": link.capacity,
                    "modes": link.modes,
                    "path": [
                        local(selected_nodes[link.from_node]),
                        local(selected_nodes[link.to_node]),
                    ],
                }
                for link in selected_links
            ]

            stands = [
                {
                    **stand,
                    "position": local(tuple(stand["center"])),
                }
                for stand in item.get("stands", [])
            ]
            fatos = [
                {
                    **fato,
                    "position": local(tuple(fato["center"])),
                }
                for fato in item.get("fatos", [])
            ]
            local_points = [
                node["position"] for node in graph_nodes
            ] + [stand["position"] for stand in stands] + [
                fato["position"] for fato in fatos
            ]
            results.append(
                {
                    "id": vertiport_id,
                    "name": configured_names.get(
                        vertiport_id, f"Vertiport {vertiport_id}"
                    ),
                    "standCount": item.get("stand_count", len(stands)),
                    "stationStandId": item.get("station_stand_id"),
                    "fatoCount": item.get("fato_count", len(fatos)),
                    "fatoCapacityVehPerHour": item.get(
                        "aggregate_fato_capacity_veh_h", 0
                    ),
                    "groundTaxiRouteWidthM": item.get(
                        "ground_taxi_route_width_m", 0
                    ),
                    "airTaxiRouteWidthM": item.get("air_taxi_route_width_m", 0),
                    "stands": stands,
                    "fatos": fatos,
                    "nodes": graph_nodes,
                    "links": graph_links,
                    "bounds": self._local_bounds(local_points),
                }
            )
        return results

    @staticmethod
    def _node_belongs_to_vertiport(node_id: str, vertiport_id: str) -> bool:
        match = VERTIPORT_NODE_PATTERN.match(node_id)
        return bool(match and match.group(1) == vertiport_id)

    @staticmethod
    def _node_kind(node_id: str) -> str:
        for kind in ("terminal", "security", "gate", "apron", "fato", "stand"):
            if f"_{kind}_" in node_id:
                return kind
        if "airborne" in node_id:
            return "airborne"
        return "network"

    @staticmethod
    def _node_label(node_id: str) -> str:
        label = node_id.replace("vt_", "").replace("_dummy", "").replace("_", " ")
        return label.title()

    @staticmethod
    def _bounds(points: list[list[float]]) -> dict[str, float]:
        if not points:
            return {"west": -0.2, "south": 51.3, "east": 0.6, "north": 51.6}
        longitudes = [point[0] for point in points]
        latitudes = [point[1] for point in points]
        return {
            "west": min(longitudes),
            "south": min(latitudes),
            "east": max(longitudes),
            "north": max(latitudes),
        }

    @staticmethod
    def _local_bounds(points: list[list[float]]) -> dict[str, float]:
        if not points:
            return {"minX": 0, "minY": 0, "maxX": 1, "maxY": 1}
        return {
            "minX": min(point[0] for point in points),
            "minY": min(point[1] for point in points),
            "maxX": max(point[0] for point in points),
            "maxY": max(point[1] for point in points),
        }

    def _write_tabular_exports(self, bundle: dict[str, Any]) -> list[str]:
        """Write Parquet tables when PyArrow is present; JSON remains canonical."""

        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.warnings.append(
                "PyArrow is not installed; browser JSON was created but Parquet "
                "analytics tables were skipped."
            )
            return []

        table_names = []

        queue_path = self.paths.output_dir / "queue_series.parquet"
        pq.write_table(pa.Table.from_pylist(bundle["queueSeries"]), queue_path)
        table_names.append(queue_path.name)

        outcome_path = self.paths.output_dir / "traveller_outcomes.parquet"
        pq.write_table(pa.Table.from_pylist(bundle["journeys"]), outcome_path)
        table_names.append(outcome_path.name)

        capacity_path = self.paths.output_dir / "capacity_series.parquet"
        pq.write_table(pa.Table.from_pylist(bundle["capacity"]["series"]), capacity_path)
        table_names.append(capacity_path.name)

        headway_rows = bundle["capacity"]["headwaySeries"]
        if headway_rows:
            headway_path = self.paths.output_dir / "fato_headway_series.parquet"
            pq.write_table(pa.Table.from_pylist(headway_rows), headway_path)
            table_names.append(headway_path.name)

        trajectory_rows = []
        for trajectory in bundle["trajectories"]:
            for sequence, (position, time_value) in enumerate(
                zip(trajectory["path"], trajectory["timestamps"])
            ):
                trajectory_rows.append(
                    {
                        "trajectoryId": trajectory["id"],
                        "vehicleId": trajectory["vehicleId"],
                        "mode": trajectory["mode"],
                        "isBackground": trajectory["isBackground"],
                        "sequence": sequence,
                        "time": time_value,
                        "longitude": position[0],
                        "latitude": position[1],
                    }
                )
        trajectory_path = self.paths.output_dir / "trajectory_points.parquet"
        pq.write_table(pa.Table.from_pylist(trajectory_rows), trajectory_path)
        table_names.append(trajectory_path.name)
        return table_names



"""Discover MATSim iterations and read the standard run-summary tables."""


import csv
import re
from dataclasses import replace
from pathlib import Path
from typing import Any



ITERATION_DIRECTORY = re.compile(r"^it\.(\d+)$")


def discover_iterations(paths: ExtractionPaths) -> list[dict[str, Any]]:
    """Return every iteration that has an events file, in numeric order."""

    iterations_root = paths.events.parent / "ITERS"
    discovered: list[dict[str, Any]] = []
    if not iterations_root.exists():
        return discovered

    for directory in iterations_root.iterdir():
        match = ITERATION_DIRECTORY.match(directory.name)
        if not directory.is_dir() or not match:
            continue
        number = int(match.group(1))
        events = directory / f"{number}.events.xml.gz"
        if not events.exists():
            events = directory / f"{number}.events.xml"
        if not events.exists():
            continue
        discovered.append(
            {
                "number": number,
                "label": f"Iteration {number}",
                "eventsFile": events.name,
                "eventsPath": events,
            }
        )

    return sorted(discovered, key=lambda item: item["number"])


def public_iteration_catalog(paths: ExtractionPaths) -> dict[str, Any]:
    """Build the browser-safe iteration catalogue."""

    iterations = discover_iterations(paths)
    default_iteration = iterations[-1]["number"] if iterations else None
    return {
        "defaultIteration": default_iteration,
        "iterations": [
            {
                "number": item["number"],
                "label": item["label"],
                "eventsFile": item["eventsFile"],
            }
            for item in iterations
        ],
    }


def paths_for_iteration(paths: ExtractionPaths, iteration: int) -> ExtractionPaths:
    """Return isolated extraction paths for one available MATSim iteration."""

    match = next(
        (
            item
            for item in discover_iterations(paths)
            if item["number"] == iteration
        ),
        None,
    )
    if match is None:
        raise KeyError(f"MATSim iteration {iteration} is not available")
    return replace(
        paths,
        events=match["eventsPath"],
        output_dir=paths.output_dir / "iterations" / f"it.{iteration}",
    )


def _read_semicolon_table(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter=";"))


def _number(value: str | None) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


def _duration_seconds(value: str | None) -> float:
    if not value:
        return 0.0
    if ":" not in value:
        return _number(value)
    try:
        hours, minutes, seconds = (float(part) for part in value.split(":"))
    except (TypeError, ValueError):
        return 0.0
    return hours * 3600 + minutes * 60 + seconds


def _read_runtime(path: Path) -> list[dict[str, float | int]]:
    """Read stopwatch.csv without losing its duplicated 'iteration' header."""

    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, delimiter=";")
        try:
            header = next(reader)
        except StopIteration:
            return []
        mobsim_index = header.index("mobsim")
        replanning_index = header.index("replanning")
        return [
            {
                "iteration": int(_number(row[0])),
                "totalSeconds": _duration_seconds(row[-1]),
                "mobsimSeconds": _duration_seconds(row[mobsim_index]),
                "replanningSeconds": _duration_seconds(row[replanning_index]),
            }
            for row in reader
            if row
        ]


def _iteration(row: dict[str, str]) -> int:
    return int(_number(row.get("iteration") or row.get("Iteration") or row.get("ITERATION")))


def _read_trip_time_stats(
    paths: ExtractionPaths,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Calculate mean trip and waiting times by main mode for each iteration.

    MATSim writes one ``N.trips.csv.gz`` table inside each iteration directory.
    Reading those tables gives an exact per-trip mean; the aggregate
    ``ph_modestats.csv`` table contains totals and cannot provide a reliable
    average without the corresponding trip counts.
    """

    results: list[dict[str, Any]] = []
    all_modes: set[str] = set()
    for item in discover_iterations(paths):
        iteration = item["number"]
        directory = item["eventsPath"].parent
        compressed_path = directory / f"{iteration}.trips.csv.gz"
        plain_path = directory / f"{iteration}.trips.csv"
        trip_path = compressed_path if compressed_path.exists() else plain_path
        if not trip_path.exists():
            continue

        travel_seconds: defaultdict[str, float] = defaultdict(float)
        wait_seconds: defaultdict[str, float] = defaultdict(float)
        trip_counts: Counter[str] = Counter()
        opener = gzip.open if trip_path.suffix.lower() == ".gz" else open
        with opener(trip_path, "rt", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream, delimiter=";"):
                mode = (
                    row.get("main_mode")
                    or row.get("longest_distance_mode")
                    or ""
                ).strip()
                if not mode:
                    continue
                trip_counts[mode] += 1
                travel_seconds[mode] += _duration_seconds(row.get("trav_time"))
                wait_seconds[mode] += _duration_seconds(row.get("wait_time"))

        if not trip_counts:
            continue
        modes = sorted(trip_counts)
        all_modes.update(modes)
        results.append(
            {
                "iteration": iteration,
                "averageTravelMinutes": {
                    mode: travel_seconds[mode] / trip_counts[mode] / 60.0
                    for mode in modes
                },
                "averageWaitMinutes": {
                    mode: wait_seconds[mode] / trip_counts[mode] / 60.0
                    for mode in modes
                },
                "tripCounts": dict(trip_counts),
            }
        )

    return results, sorted(all_modes)


def read_general_results(paths: ExtractionPaths) -> dict[str, Any]:
    """Read the standard MATSim CSV outputs into one dashboard payload."""

    root = paths.events.parent
    source_files: list[str] = []

    def table(name: str) -> list[dict[str, str]]:
        path = root / name
        rows = _read_semicolon_table(path)
        if rows:
            source_files.append(name)
        return rows

    score_rows = table("scorestats.csv")
    mode_rows = table("modestats.csv")
    passenger_hour_rows = table("ph_modestats.csv")
    passenger_km_rows = table("pkm_modestats.csv")
    distance_rows = table("traveldistancestats.csv")
    runtime_path = root / "stopwatch.csv"
    runtime = _read_runtime(runtime_path)
    if runtime:
        source_files.append(runtime_path.name)
    trip_time_stats, trip_time_modes = _read_trip_time_stats(paths)
    if trip_time_stats:
        source_files.append("ITERS/it.N/N.trips.csv.gz")

    score_stats = [
        {
            "iteration": _iteration(row),
            "avgExecuted": _number(row.get("avg_executed")),
            "avgWorst": _number(row.get("avg_worst")),
            "avgAverage": _number(row.get("avg_average")),
            "avgBest": _number(row.get("avg_best")),
        }
        for row in score_rows
    ]

    mode_columns = sorted(
        {
            key
            for row in mode_rows
            for key in row
            if key.lower() != "iteration" and key
        }
    )
    mode_share = [
        {
            "iteration": _iteration(row),
            "values": {mode: _number(row.get(mode)) for mode in mode_columns},
        }
        for row in mode_rows
    ]

    passenger_km_columns = sorted(
        {
            key
            for row in passenger_km_rows
            for key in row
            if key.lower() != "iteration" and key
        }
    )
    passenger_km = [
        {
            "iteration": _iteration(row),
            "values": {
                mode: _number(row.get(mode)) for mode in passenger_km_columns
            },
        }
        for row in passenger_km_rows
    ]

    passenger_hours = []
    for row in passenger_hour_rows:
        modes = sorted(
            {
                key.rsplit("_", 1)[0]
                for key in row
                if key and key.lower() != "iteration" and "_" in key
            }
        )
        passenger_hours.append(
            {
                "iteration": _iteration(row),
                "travel": {
                    mode: _number(row.get(f"{mode}_travel")) for mode in modes
                },
                "wait": {
                    mode: _number(row.get(f"{mode}_wait")) for mode in modes
                },
            }
        )

    travel_distance = [
        {
            "iteration": _iteration(row),
            "avgLegKm": _number(row.get("avg. Average Leg distance")) / 1000,
            "avgTripKm": _number(row.get("avg. Average Trip distance")) / 1000,
        }
        for row in distance_rows
    ]

    available_iterations = [
        item["number"] for item in discover_iterations(paths)
    ]
    return {
        "availableIterations": available_iterations,
        "scoreStats": score_stats,
        "modeShare": mode_share,
        "modeNames": mode_columns,
        "passengerKilometres": passenger_km,
        "passengerKilometreModes": passenger_km_columns,
        "passengerHours": passenger_hours,
        "tripTimeStats": trip_time_stats,
        "tripTimeModes": trip_time_modes,
        "travelDistance": travel_distance,
        "runtime": runtime,
        "sourceFiles": source_files,
    }



"""FastAPI server for Module 5 analytics and its compiled frontend."""


import json
from pathlib import Path



def create_app(
    paths: ExtractionPaths,
    *,
    crs: str | None = None,
    frontend_dist: Path | None = None,
    force_extract: bool = False,
    cache_only: bool = False,
    extract_missing_iterations: bool = False,
    scenario_name: str | None = None,
):
    try:
        from fastapi import FastAPI, HTTPException, Query
        from fastapi.middleware.gzip import GZipMiddleware
        from fastapi.responses import FileResponse, JSONResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:
        raise RuntimeError(
            "FastAPI is required to serve Module 5. "
            "Install dependencies from module5/requirements.txt."
        ) from exc

    extractor = (
        AnalyticsExtractor(paths, crs=crs)
        if not cache_only or extract_missing_iterations
        else None
    )
    bundle_path = paths.output_dir / "analytics_bundle.json"
    manifest_path = paths.output_dir / "manifest.json"
    if cache_only:
        missing_cache_files = [
            path for path in (bundle_path, manifest_path) if not path.is_file()
        ]
        if missing_cache_files:
            missing = "\n".join(str(path) for path in missing_cache_files)
            raise FileNotFoundError(
                "Module 5 cache-only mode requires an existing analytics "
                f"bundle and manifest. Missing:\n{missing}\n"
                "Run `python -m module5 extract` once to build the cache."
            )
    else:
        assert extractor is not None
        bundle_path = extractor.extract(force=force_extract)
    dist = frontend_dist or Path(__file__).resolve().parent / "module5" / "frontend" / "dist"
    iteration_catalog = public_iteration_catalog(paths)
    iteration_catalog["scenarioName"] = scenario_name
    default_iteration = iteration_catalog["defaultIteration"]
    if cache_only and not extract_missing_iterations:
        iteration_catalog["iterations"] = [
            item
            for item in iteration_catalog["iterations"]
            if item["number"] == default_iteration
            or (
                paths.output_dir
                / "iterations"
                / f"it.{item['number']}"
                / "analytics_bundle.json"
            ).is_file()
        ]

    app = FastAPI(
        title="UAM Scenario Toolkit — Module 5",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "module": 5,
            "schemaVersion": SCHEMA_VERSION,
            "bundle": bundle_path.name,
            "scenarioName": scenario_name,
            "cacheOnly": cache_only,
            "extractMissingIterations": extract_missing_iterations,
        }

    @app.get("/api/manifest")
    def manifest():
        return JSONResponse(
            json.loads(manifest_path.read_text(encoding="utf-8"))
        )

    @app.get("/api/analytics")
    def analytics(iteration: int | None = Query(default=None, ge=0)):
        selected_bundle = bundle_path
        # MATSim's top-level output_events file represents the final iteration,
        # and the pipeline has already extracted it into ``bundle_path``.  Do
        # not parse the same (potentially very large) event stream again when
        # the browser requests the default/final iteration on first load.
        if iteration is not None and iteration != default_iteration:
            try:
                selected_paths = paths_for_iteration(paths, iteration)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            selected_bundle = selected_paths.output_dir / "analytics_bundle.json"
            if cache_only:
                if selected_bundle.is_file():
                    pass
                elif extract_missing_iterations:
                    assert extractor is not None
                    selected_bundle = AnalyticsExtractor(
                        selected_paths, crs=extractor.crs
                    ).extract()
                else:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"MATSim iteration {iteration} is not cached. "
                            "Restart without --cache-only to prepare it."
                        ),
                    )
            else:
                assert extractor is not None
                selected_bundle = AnalyticsExtractor(
                    selected_paths, crs=extractor.crs
                ).extract()
        return FileResponse(
            selected_bundle,
            media_type="application/json",
            filename=selected_bundle.name,
        )

    @app.get("/api/iterations")
    def iterations():
        return JSONResponse(iteration_catalog)

    @app.get("/api/matsim-results")
    def matsim_results():
        return JSONResponse(read_general_results(paths))

    if dist.exists() and (dist / "index.html").exists():
        assets = dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{requested_path:path}")
        def frontend(requested_path: str):
            candidate = (dist / requested_path).resolve()
            try:
                candidate.relative_to(dist.resolve())
            except ValueError:
                return JSONResponse({"detail": "Invalid path"}, status_code=400)
            if requested_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")
    else:

        @app.get("/")
        def frontend_missing():
            return JSONResponse(
                {
                    "status": "analytics API ready",
                    "message": (
                        "The frontend has not been built. Run npm install and "
                        "pnpm run build in src/module5/frontend."
                    ),
                    "analytics": "/api/analytics",
                    "docs": "/api/docs",
                }
            )

    return app



"""Command-line entry point for Module 5."""


import argparse
import threading
import webbrowser
from pathlib import Path



def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_manifest(run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _scenario_name_from_args(args: argparse.Namespace) -> str | None:
    run_dir_value = getattr(args, "run_dir", None)
    if not run_dir_value:
        config = _runtime_config()
        name = getattr(config, "SCENARIO_NAME", "") if config is not None else ""
        return str(name).strip() or None
    run_dir = Path(run_dir_value).resolve()
    run_id = _run_manifest(run_dir).get("run_id")
    return str(run_id or run_dir.name)


def _background_traffic_from_run(run_dir: Path) -> bool:
    manifest = _run_manifest(run_dir)
    effective = manifest.get("effective_parameters")
    if isinstance(effective, dict):
        try:
            if int(effective.get("background_agents") or 0) > 0:
                return True
        except (TypeError, ValueError):
            pass
        if str(effective.get("background_population_path") or "").strip():
            return True
    overrides = manifest.get("overrides")
    if isinstance(overrides, dict):
        try:
            return int(overrides.get("background_agents") or 0) > 0
        except (TypeError, ValueError):
            return False
    return False


def _paths_from_args(args: argparse.Namespace) -> ExtractionPaths:
    root = _project_root()
    config = _runtime_config()
    run_dir_value = getattr(args, "run_dir", None)
    run_dir = Path(run_dir_value).resolve() if run_dir_value else None
    results_dir = run_dir / "outputs" if run_dir else root / "outputs"
    snapshots_dir = run_dir / "input_snapshots" if run_dir else root / "scenarios"
    default_design_report = (
        snapshots_dir / "vertiport_design_report.json"
        if run_dir
        else snapshots_dir / "networks" / "vertiport_design_report.json"
    )
    default_population = (
        snapshots_dir / "population.xml"
        if run_dir
        else snapshots_dir / "populations" / "population.xml"
    )

    background_override = getattr(args, "background_traffic", None)
    if background_override is not None:
        background_traffic_enabled = bool(background_override)
    elif run_dir is not None:
        background_traffic_enabled = _background_traffic_from_run(run_dir)
    else:
        background_traffic_enabled = bool(
            str(getattr(config, "BASE_POPULATION_PATH", "")).strip()
        ) if config is not None else False

    return ExtractionPaths(
        events=Path(args.events or results_dir / "output_events.xml.gz").resolve(),
        network=Path(args.network or results_dir / "output_network.xml.gz").resolve(),
        design_report=Path(
            args.design_report or default_design_report
        ).resolve(),
        population=Path(args.population or default_population).resolve(),
        output_dir=Path(
            args.output_dir or results_dir / "module5_analytics"
        ).resolve(),
        background_traffic_enabled=background_traffic_enabled,
    )


def _common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--run-dir",
        help=(
            "Archived run directory containing outputs/ and input_snapshots/. "
            "Explicit file arguments override paths discovered from this directory."
        ),
    )
    parser.add_argument("--events", help="MATSim output_events.xml(.gz)")
    parser.add_argument("--network", help="MATSim output_network.xml(.gz)")
    parser.add_argument("--design-report", help="vertiport_design_report.json")
    parser.add_argument("--population", help="Population XML used for this run")
    parser.add_argument("--output-dir", help="Analytics cache/output directory")
    parser.add_argument(
        "--crs",
        help="Coordinate reference system of the MATSim network (defaults to MODULE5_CRS)",
    )
    parser.add_argument("--force", action="store_true", help="Ignore cached extraction")
    background = parser.add_mutually_exclusive_group()
    background.add_argument(
        "--background-traffic",
        dest="background_traffic",
        action="store_true",
        help="Mark generated road-demand agents as background traffic.",
    )
    background.add_argument(
        "--no-background-traffic",
        dest="background_traffic",
        action="store_false",
        help="Disable background-traffic markers.",
    )
    parser.set_defaults(background_traffic=None)


def _serve_arguments(parser: argparse.ArgumentParser) -> None:
    _common_arguments(parser)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help=(
            "Serve an existing analytics bundle without parsing MATSim files. "
            "Useful for reopening archived runs."
        ),
    )
    parser.add_argument(
        "--extract-missing-iterations",
        action="store_true",
        help=(
            "With --cache-only, expose every iteration and build only a "
            "selected iteration when its analytics cache is missing. MATSim "
            "is not rerun, and each extracted iteration is cached."
        ),
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the application in the default browser.",
    )


def build_parser(prog: str = "python -m module5") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="UST Module 5 analytics extraction and application server.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    extract = subcommands.add_parser("extract", help="Build analytics files")
    _common_arguments(extract)

    serve = subcommands.add_parser("serve", help="Build analytics and serve the UI")
    _serve_arguments(serve)
    return parser


def build_server_parser(
    prog: str = "python src/local_server.py",
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Serve the UST Module 5 analytics dashboard locally.",
    )
    _serve_arguments(parser)
    parser.set_defaults(command="serve")
    return parser


def _run_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.command == "serve" and args.cache_only and args.force:
        parser.error("--cache-only and --force cannot be used together")
    if (
        args.command == "serve"
        and args.extract_missing_iterations
        and not args.cache_only
    ):
        parser.error("--extract-missing-iterations requires --cache-only")
    paths = _paths_from_args(args)

    if args.command == "extract":
        result = AnalyticsExtractor(paths, crs=args.crs).extract(force=args.force)
        print(f"[Module 5] Analytics bundle written to:\n{result}")
        return 0

    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError(
            "Uvicorn is required to serve Module 5. "
            "Install dependencies from module5/requirements.txt."
        ) from exc

    scenario_name = _scenario_name_from_args(args)
    app = create_app(
        paths,
        crs=args.crs,
        force_extract=args.force,
        cache_only=args.cache_only,
        extract_missing_iterations=args.extract_missing_iterations,
        scenario_name=scenario_name,
    )
    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    scenario_suffix = f" ({scenario_name})" if scenario_name else ""
    print(f"[Module 5] Analytics available at {url}{scenario_suffix}")
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def main(
    argv: list[str] | None = None,
    *,
    prog: str = "python -m module5",
) -> int:
    parser = build_parser(prog=prog)
    return _run_command(parser.parse_args(argv), parser)


def server_main(
    argv: list[str] | None = None,
    *,
    prog: str = "python src/local_server.py",
) -> int:
    parser = build_server_parser(prog=prog)
    return _run_command(parser.parse_args(argv), parser)



if __name__ == "__main__":
    raise SystemExit(main())
