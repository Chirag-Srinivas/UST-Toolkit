r"""Generate a standalone MATSim background-road-traffic population.

The generator is intentionally not imported by ``pipeline.py``.  It samples
links from the cleaned road network that the pipeline actually retains, while
always writing its MATSim population XML beside the configured raw base
network (the project's ``data`` folder).  Each synthetic person makes an
outward morning-peak car trip and a return evening-peak trip.

Example from ``src``::

    ..\venv\Scripts\python.exe background_traffic_generator.py --agents 5000

The output can later be used as ``BASE_POPULATION_PATH`` if background traffic
is deliberately enabled.  Synthetic demand should be calibrated against
counts or an OD matrix before it is treated as representative of real traffic.
"""

from __future__ import annotations

import argparse
import gzip
import math
import random
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable, TextIO
from xml.sax.saxutils import quoteattr

import config


DEFAULT_OUTPUT_NAME = "background_traffic.xml"
DEFAULT_AGENTS = 5_000
DEFAULT_CANDIDATE_LINKS = 20_000
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SIMULATION_NETWORK_PATH = (
    PROJECT_ROOT / "scenarios" / "networks" / "base_network_cleaned.xml"
)
BASE_DATA_DIRECTORY = Path(config.BASE_NETWORK_PATH).expanduser().resolve().parent


@dataclass(frozen=True)
class RoadLink:
    """A car-enabled MATSim link and its activity coordinate."""

    id: str
    from_node: str
    to_node: str
    x: float
    y: float


@dataclass(frozen=True)
class SampledLink:
    """Link metadata retained during the first streaming network pass."""

    id: str
    from_node: str
    to_node: str


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _open_network(path: Path) -> BinaryIO:
    return gzip.open(path, "rb") if path.suffix.lower() == ".gz" else path.open("rb")


def _allows_car(modes: str | None) -> bool:
    return "car" in {
        mode for mode in re.split(r"[,;\s]+", (modes or "").lower()) if mode
    }


def _build_car_graph(
    network_path: Path,
) -> tuple[dict[str, list[str]], dict[str, list[str]], int]:
    """Build the directed car graph needed for a strong-connectivity check."""

    adjacency: defaultdict[str, list[str]] = defaultdict(list)
    reverse: defaultdict[str, list[str]] = defaultdict(list)
    car_link_count = 0
    with _open_network(network_path) as stream:
        for _, element in ET.iterparse(stream, events=("end",)):
            if _local_name(element.tag) == "link" and _allows_car(
                element.attrib.get("modes")
            ):
                from_node = element.attrib["from"]
                to_node = element.attrib["to"]
                adjacency[from_node].append(to_node)
                reverse[to_node].append(from_node)
                car_link_count += 1
            element.clear()
    return dict(adjacency), dict(reverse), car_link_count


def _finishing_order(
    nodes: set[str], adjacency: dict[str, list[str]]
) -> list[str]:
    """Return iterative DFS finishing order without recursion-depth limits."""

    visited: set[str] = set()
    order: list[str] = []
    for start in nodes:
        if start in visited:
            continue
        visited.add(start)
        stack: list[tuple[str, int]] = [(start, 0)]
        while stack:
            node, index = stack[-1]
            neighbours = adjacency.get(node, [])
            if index < len(neighbours):
                neighbour = neighbours[index]
                stack[-1] = (node, index + 1)
                if neighbour not in visited:
                    visited.add(neighbour)
                    stack.append((neighbour, 0))
            else:
                stack.pop()
                order.append(node)
    return order


def _largest_strongly_connected_component(
    adjacency: dict[str, list[str]], reverse: dict[str, list[str]]
) -> set[str]:
    """Find the largest directed component using iterative Kosaraju passes."""

    nodes = set(adjacency) | set(reverse)
    order = _finishing_order(nodes, adjacency)
    assigned: set[str] = set()
    largest: set[str] = set()
    for start in reversed(order):
        if start in assigned:
            continue
        component: set[str] = set()
        stack = [start]
        assigned.add(start)
        while stack:
            node = stack.pop()
            component.add(node)
            for neighbour in reverse.get(node, []):
                if neighbour not in assigned:
                    assigned.add(neighbour)
                    stack.append(neighbour)
        if len(component) > len(largest):
            largest = component
    return largest


def _reservoir_sample_component_links(
    network_path: Path,
    component_nodes: set[str],
    sample_size: int,
    rng: random.Random,
) -> tuple[list[SampledLink], int]:
    """Uniformly sample car links wholly inside the routable component."""

    reservoir: list[SampledLink] = []
    routable_link_count = 0
    with _open_network(network_path) as stream:
        for _, element in ET.iterparse(stream, events=("end",)):
            if _local_name(element.tag) == "link" and _allows_car(
                element.attrib.get("modes")
            ):
                from_node = element.attrib["from"]
                to_node = element.attrib["to"]
                if from_node in component_nodes and to_node in component_nodes:
                    candidate = SampledLink(
                        id=element.attrib["id"],
                        from_node=from_node,
                        to_node=to_node,
                    )
                    routable_link_count += 1
                    if len(reservoir) < sample_size:
                        reservoir.append(candidate)
                    else:
                        replacement = rng.randrange(routable_link_count)
                        if replacement < sample_size:
                            reservoir[replacement] = candidate
            element.clear()
    return reservoir, routable_link_count


def _load_sampled_link_coordinates(
    network_path: Path, sampled_links: Iterable[SampledLink]
) -> list[RoadLink]:
    """Read only the nodes needed to position the sampled links."""

    sampled_links = list(sampled_links)
    required_nodes = {
        node_id
        for link in sampled_links
        for node_id in (link.from_node, link.to_node)
    }
    coordinates: dict[str, tuple[float, float]] = {}
    with _open_network(network_path) as stream:
        for _, element in ET.iterparse(stream, events=("end",)):
            if _local_name(element.tag) == "node":
                node_id = element.attrib.get("id")
                if node_id in required_nodes:
                    coordinates[node_id] = (
                        float(element.attrib["x"]),
                        float(element.attrib["y"]),
                    )
                    if len(coordinates) == len(required_nodes):
                        break
            element.clear()

    missing = required_nodes - coordinates.keys()
    if missing:
        examples = ", ".join(sorted(missing)[:5])
        raise ValueError(
            f"The network is missing {len(missing)} node(s) referenced by sampled "
            f"car links (for example: {examples})."
        )

    road_links = []
    for link in sampled_links:
        from_x, from_y = coordinates[link.from_node]
        to_x, to_y = coordinates[link.to_node]
        road_links.append(
            RoadLink(
                id=link.id,
                from_node=link.from_node,
                to_node=link.to_node,
                x=(from_x + to_x) / 2.0,
                y=(from_y + to_y) / 2.0,
            )
        )
    return road_links


def sample_car_links(
    network_path: Path,
    sample_size: int,
    rng: random.Random,
) -> tuple[list[RoadLink], int, int]:
    """Return a memory-bounded pool of activity links and total car-link count."""

    if sample_size < 2:
        raise ValueError("candidate_links must be at least 2")
    print(f"[Background traffic] Reading directed car graph from {network_path}")
    adjacency, reverse, car_link_count = _build_car_graph(network_path)
    if car_link_count < 2:
        raise ValueError(f"Network contains only {car_link_count} car-enabled link(s)")
    component_nodes = _largest_strongly_connected_component(adjacency, reverse)
    del adjacency, reverse
    sampled, routable_link_count = _reservoir_sample_component_links(
        network_path, component_nodes, sample_size, rng
    )
    if routable_link_count < 2:
        raise ValueError(
            "The largest strongly connected car component contains fewer than "
            "two links"
        )
    print(
        f"[Background traffic] Largest routable car component: "
        f"{len(component_nodes):,} nodes / {routable_link_count:,} links "
        f"({car_link_count:,} car links before filtering); retained "
        f"{len(sampled):,} candidates"
    )
    return (
        _load_sampled_link_coordinates(network_path, sampled),
        car_link_count,
        routable_link_count,
    )


def _distance_metres(first: RoadLink, second: RoadLink) -> float:
    return math.hypot(second.x - first.x, second.y - first.y)


def choose_destination(
    origin: RoadLink,
    candidates: list[RoadLink],
    rng: random.Random,
    *,
    median_distance_m: float,
    minimum_distance_m: float,
    maximum_distance_m: float,
    attempts: int = 48,
) -> RoadLink:
    """Choose a link close to a bounded log-normal target trip distance."""

    target_distance = min(
        maximum_distance_m,
        max(
            minimum_distance_m,
            rng.lognormvariate(math.log(median_distance_m), 0.55),
        ),
    )
    best: RoadLink | None = None
    best_error = math.inf
    for candidate in rng.choices(candidates, k=attempts):
        if candidate.id == origin.id:
            continue
        distance = _distance_metres(origin, candidate)
        if not minimum_distance_m <= distance <= maximum_distance_m:
            continue
        error = abs(math.log(max(distance, 1.0) / target_distance))
        if error < best_error:
            best = candidate
            best_error = error
    if best is None:
        raise ValueError(
            "Could not find an origin/destination pair in the requested distance "
            "range. Increase --candidate-links or widen the distance bounds."
        )
    return best


def _clipped_gaussian(
    rng: random.Random, mean_seconds: float, spread_seconds: float
) -> float:
    return min(30 * 3600.0, max(0.0, rng.gauss(mean_seconds, spread_seconds)))


def _time_string(seconds: float) -> str:
    rounded = max(0, int(round(seconds)))
    hours, remainder = divmod(rounded, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _write_activity(
    stream: TextIO,
    *,
    activity_type: str,
    link: RoadLink,
    end_time: str | None = None,
) -> None:
    attributes = (
        f" type={quoteattr(activity_type)} link={quoteattr(link.id)}"
        f" x={quoteattr(f'{link.x:.3f}')} y={quoteattr(f'{link.y:.3f}')}"
    )
    if end_time is not None:
        attributes += f" end_time={quoteattr(end_time)}"
    stream.write(f"      <activity{attributes} />\n")


def write_background_population(
    output_path: Path,
    links: list[RoadLink],
    *,
    agents: int,
    rng: random.Random,
    seed: int,
    median_distance_km: float,
    minimum_distance_km: float,
    maximum_distance_km: float,
    morning_peak_hour: float,
    evening_peak_hour: float,
    peak_spread_minutes: float,
    overwrite: bool = False,
) -> dict[str, float | int | str]:
    """Stream a two-trip commuter population to a MATSim v6 XML file."""

    if agents < 1:
        raise ValueError("agents must be at least 1")
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Output already exists: {output_path}. Pass --overwrite to replace it."
        )

    minimum_distance_m = minimum_distance_km * 1000.0
    median_distance_m = median_distance_km * 1000.0
    maximum_distance_m = maximum_distance_km * 1000.0
    if not 0 < minimum_distance_m <= median_distance_m <= maximum_distance_m:
        raise ValueError(
            "Distance bounds must satisfy 0 < minimum <= median <= maximum"
        )
    if peak_spread_minutes < 0:
        raise ValueError("peak_spread_minutes cannot be negative")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    total_distance_m = 0.0
    min_observed_m = math.inf
    max_observed_m = 0.0
    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write('<?xml version="1.0" encoding="utf-8"?>\n')
            stream.write(
                '<!DOCTYPE population SYSTEM '
                '"http://www.matsim.org/files/dtd/population_v6.dtd" [\n'
                '  <!ATTLIST leg routingMode CDATA #IMPLIED>\n'
                ']>\n'
            )
            stream.write("<population>\n")
            stream.write(
                "  <!-- Uncalibrated commuter demand: "
                f"agents={agents}, seed={seed}. -->\n"
            )
            for index in range(1, agents + 1):
                origin = rng.choice(links)
                destination = choose_destination(
                    origin,
                    links,
                    rng,
                    median_distance_m=median_distance_m,
                    minimum_distance_m=minimum_distance_m,
                    maximum_distance_m=maximum_distance_m,
                )
                distance_m = _distance_metres(origin, destination)
                total_distance_m += distance_m
                min_observed_m = min(min_observed_m, distance_m)
                max_observed_m = max(max_observed_m, distance_m)

                spread_seconds = peak_spread_minutes * 60.0
                morning_departure = _clipped_gaussian(
                    rng, morning_peak_hour * 3600.0, spread_seconds
                )
                evening_departure = _clipped_gaussian(
                    rng, evening_peak_hour * 3600.0, spread_seconds
                )
                evening_departure = max(
                    evening_departure, morning_departure + 4 * 3600.0
                )

                person_id = f"background_car_{index:07d}"
                stream.write(f"  <person id={quoteattr(person_id)}>\n")
                stream.write("    <attributes>\n")
                stream.write(
                    '      <attribute name="subpopulation" '
                    'class="java.lang.String">default</attribute>\n'
                )
                stream.write(
                    '      <attribute name="backgroundTraffic" '
                    'class="java.lang.Boolean">true</attribute>\n'
                )
                stream.write("    </attributes>\n")
                stream.write('    <plan selected="yes">\n')
                _write_activity(
                    stream,
                    activity_type="dummyorigin",
                    link=origin,
                    end_time=_time_string(morning_departure),
                )
                stream.write('      <leg mode="car" routingMode="car" />\n')
                _write_activity(
                    stream,
                    activity_type="dummydestination",
                    link=destination,
                    end_time=_time_string(evening_departure),
                )
                stream.write('      <leg mode="car" routingMode="car" />\n')
                _write_activity(
                    stream, activity_type="dummyorigin", link=origin
                )
                stream.write("    </plan>\n")
                stream.write("  </person>\n")
            stream.write("</population>\n")
        temporary_path.replace(output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return {
        "agents": agents,
        "trips": agents * 2,
        "meanEuclideanDistanceKm": total_distance_m / agents / 1000.0,
        "minimumEuclideanDistanceKm": min_observed_m / 1000.0,
        "maximumEuclideanDistanceKm": max_observed_m / 1000.0,
        "output": str(output_path),
    }


def _output_path(output_directory: Path, output_name: str) -> Path:
    requested = Path(output_name)
    if requested.name != output_name or requested.suffix.lower() != ".xml":
        raise ValueError("--output must be a plain .xml filename without a directory")
    return output_directory / requested.name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate uncalibrated, two-peak MATSim car demand beside the base "
            "network. This tool is not part of pipeline.py."
        )
    )
    parser.add_argument(
        "--network",
        type=Path,
        default=DEFAULT_SIMULATION_NETWORK_PATH,
        help=(
            "Cleaned MATSim road network XML/XML.GZ used for link sampling "
            "(default: scenarios/networks/base_network_cleaned.xml)"
        ),
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_NAME,
        help=(
            "Output filename only; it is always written in the configured "
            "base network's data folder "
            f"(default: {DEFAULT_OUTPUT_NAME})"
        ),
    )
    parser.add_argument(
        "--agents",
        type=int,
        default=DEFAULT_AGENTS,
        help=f"Synthetic people; each makes two car trips (default: {DEFAULT_AGENTS})",
    )
    parser.add_argument("--seed", type=int, default=4711)
    parser.add_argument(
        "--candidate-links",
        type=int,
        default=DEFAULT_CANDIDATE_LINKS,
        help="Memory-bounded reservoir of car links used for OD sampling",
    )
    parser.add_argument("--minimum-distance-km", type=float, default=1.0)
    parser.add_argument("--median-distance-km", type=float, default=8.0)
    parser.add_argument("--maximum-distance-km", type=float, default=30.0)
    parser.add_argument("--morning-peak-hour", type=float, default=8.0)
    parser.add_argument("--evening-peak-hour", type=float, default=17.5)
    parser.add_argument("--peak-spread-minutes", type=float, default=75.0)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output file",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    network_path = args.network.expanduser().resolve()
    if not network_path.is_file():
        raise FileNotFoundError(
            f"Cleaned sampling network does not exist: {network_path}. Run the "
            "pipeline's network-preparation steps first or pass --network with "
            "the exact cleaned road network used by MATSim."
        )
    output_path = _output_path(BASE_DATA_DIRECTORY, args.output)
    if output_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"Output already exists: {output_path}. Pass --overwrite to replace it."
        )
    rng = random.Random(args.seed)
    links, car_link_count, routable_link_count = sample_car_links(
        network_path, args.candidate_links, rng
    )
    summary = write_background_population(
        output_path,
        links,
        agents=args.agents,
        rng=rng,
        seed=args.seed,
        median_distance_km=args.median_distance_km,
        minimum_distance_km=args.minimum_distance_km,
        maximum_distance_km=args.maximum_distance_km,
        morning_peak_hour=args.morning_peak_hour,
        evening_peak_hour=args.evening_peak_hour,
        peak_spread_minutes=args.peak_spread_minutes,
        overwrite=args.overwrite,
    )
    print(
        "[Background traffic] Wrote "
        f"{summary['agents']:,} people / {summary['trips']:,} car trips to "
        f"{summary['output']}"
    )
    print(
        "[Background traffic] Euclidean OD distance: "
        f"mean {summary['meanEuclideanDistanceKm']:.1f} km "
        f"(range {summary['minimumEuclideanDistanceKm']:.1f}-"
        f"{summary['maximumEuclideanDistanceKm']:.1f} km); "
        f"network pool {len(links):,}/{routable_link_count:,} routable links "
        f"({car_link_count:,} before connectivity filtering)"
    )
    print(
        "[Background traffic] This is synthetic demand. Calibrate agents, "
        "departure peaks, and OD distances before interpreting congestion."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
