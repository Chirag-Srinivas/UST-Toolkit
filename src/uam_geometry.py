"""Shared geometry helpers for configurable vertiports and aerial routes.

The dimensional checks implement the simulation-relevant parts of EASA's
March 2022 prototype VFR vertiport design specification.  The prototype is
guidance, not a construction approval or a certification result.
"""

import math


FIXED_LAYOUT_POINTS = (
    "security",
    "gate",
    "apron",
    "airborne",
)


def _xy(value, label):
    """Return a validated two-dimensional coordinate tuple."""
    if isinstance(value, dict):
        value = (value.get("x"), value.get("y"))
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{label} must be an [x, y] pair or an {{'x', 'y'}} mapping.")
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} contains a non-numeric coordinate: {value!r}") from exc


def _positive(value, label):
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric.") from exc
    if value <= 0.0:
        raise ValueError(f"{label} must be greater than zero.")
    return value


def _safe_id(value, label):
    value = str(value)
    if not value or not all(char.isalnum() or char in "_.-" for char in value):
        raise ValueError(f"{label} must use only letters, numbers, '.', '_' or '-'.")
    return value


def _design_envelope(vehicle_type):
    """Return the controlling aircraft D and overall dimensions."""
    if not isinstance(vehicle_type, dict):
        raise ValueError("UAM_VEHICLE_TYPE must be a mapping.")
    length = _positive(vehicle_type.get("overall_length"), "Vehicle overall_length")
    width = _positive(vehicle_type.get("overall_width"), "Vehicle overall_width")
    return {
        "overall_length": length,
        "overall_width": width,
        "design_diameter": max(length, width),
    }


def _validated_rules(rules):
    required = (
        "fato_dimension_factor_d",
        "safety_area_margin_factor_d",
        "safety_area_margin_min_m",
        "surface_tlof_dimension_factor_d",
        "elevated_tlof_dimension_factor_d",
        "stand_dimension_factor_d",
        "stand_protection_margin_factor_d",
        "ground_taxi_route_width_factor",
        "air_taxi_route_width_factor",
    )
    if not isinstance(rules, dict):
        raise ValueError("VERTIPORT_DESIGN_RULES must be a mapping.")
    return {key: _positive(rules.get(key), f"Design rule {key}") for key in required}


def _rotate_offset(x, y, angle_deg):
    angle = math.radians(float(angle_deg))
    return (
        x * math.cos(angle) - y * math.sin(angle),
        x * math.sin(angle) + y * math.cos(angle),
    )


def _stand_geometry(layout_value, design_diameter, rules, vp_id):
    stand_dimension = rules["stand_dimension_factor_d"] * design_diameter
    protection_margin = rules["stand_protection_margin_factor_d"] * design_diameter
    protected_diameter = stand_dimension + 2.0 * protection_margin

    if isinstance(layout_value, list):
        raw_stands = layout_value
    elif isinstance(layout_value, dict):
        count = int(layout_value.get("count", 0))
        columns = int(layout_value.get("columns", 0))
        if count <= 0 or columns <= 0:
            raise ValueError(
                f"Vertiport {vp_id} stand grid requires positive count and columns."
            )
        origin = _xy(layout_value.get("origin"), f"Vertiport {vp_id} stand grid origin")
        spacing = _positive(
            layout_value.get("spacing_m", protected_diameter),
            f"Vertiport {vp_id} stand grid spacing_m",
        )
        if spacing + 1e-9 < protected_diameter:
            raise ValueError(
                f"Vertiport {vp_id} stand grid spacing {spacing:.3f} m is below "
                f"the {protected_diameter:.3f} m protected stand diameter."
            )
        angle = float(layout_value.get("orientation_deg", 0.0))
        raw_stands = []
        for index in range(count):
            column = index % columns
            row = index // columns
            dx, dy = _rotate_offset(column * spacing, row * spacing, angle)
            raw_stands.append(
                {"id": f"S{index + 1}", "center": [origin[0] + dx, origin[1] + dy]}
            )
    else:
        raise ValueError(
            f"Vertiport {vp_id} layout.stands must be a list or a grid mapping."
        )

    stands = []
    known_ids = set()
    for index, stand in enumerate(raw_stands):
        if not isinstance(stand, dict):
            stand = {"id": f"S{index + 1}", "center": stand}
        stand_id = _safe_id(stand.get("id", f"S{index + 1}"), "Stand id")
        if stand_id in known_ids:
            raise ValueError(f"Vertiport {vp_id} has duplicate stand id {stand_id}.")
        known_ids.add(stand_id)
        declared_dimension = _positive(
            stand.get("dimension_m", stand_dimension),
            f"Vertiport {vp_id} stand {stand_id} dimension_m",
        )
        if declared_dimension + 1e-9 < stand_dimension:
            raise ValueError(
                f"Vertiport {vp_id} stand {stand_id} is {declared_dimension:.3f} m; "
                f"the design minimum is {stand_dimension:.3f} m."
            )
        stands.append(
            {
                "id": stand_id,
                "center_local": _xy(
                    stand.get("center"), f"Vertiport {vp_id} stand {stand_id} center"
                ),
                "dimension_m": declared_dimension,
                "protection_margin_m": protection_margin,
                "protected_diameter_m": declared_dimension + 2.0 * protection_margin,
            }
        )

    if not stands:
        raise ValueError(f"Vertiport {vp_id} must define at least one stand.")
    return stands


def _fato_geometry(layout_value, design_diameter, rules, vp_id):
    if not isinstance(layout_value, list) or not layout_value:
        raise ValueError(f"Vertiport {vp_id} layout.fatos must be a non-empty list.")

    min_fato = rules["fato_dimension_factor_d"] * design_diameter
    safety_margin = max(
        rules["safety_area_margin_min_m"],
        rules["safety_area_margin_factor_d"] * design_diameter,
    )
    fatos = []
    known_ids = set()
    for index, fato in enumerate(layout_value):
        if not isinstance(fato, dict):
            fato = {"id": f"F{index + 1}", "center": fato}
        fato_id = _safe_id(fato.get("id", f"F{index + 1}"), "FATO id")
        if fato_id in known_ids:
            raise ValueError(f"Vertiport {vp_id} has duplicate FATO id {fato_id}.")
        known_ids.add(fato_id)

        afm_length = float(fato.get("afm_fato_length_m", 0.0))
        afm_width = float(fato.get("afm_fato_width_m", 0.0))
        required_length = max(min_fato, afm_length)
        required_width = max(min_fato, afm_width)
        declared_length = _positive(
            fato.get("length_m", required_length),
            f"Vertiport {vp_id} FATO {fato_id} length_m",
        )
        declared_width = _positive(
            fato.get("width_m", required_width),
            f"Vertiport {vp_id} FATO {fato_id} width_m",
        )
        if declared_length + 1e-9 < required_length or declared_width + 1e-9 < required_width:
            raise ValueError(
                f"Vertiport {vp_id} FATO {fato_id} is {declared_length:.3f} x "
                f"{declared_width:.3f} m; required is at least "
                f"{required_length:.3f} x {required_width:.3f} m."
            )

        elevated = bool(fato.get("elevated", False))
        tlof_factor = (
            rules["elevated_tlof_dimension_factor_d"]
            if elevated
            else rules["surface_tlof_dimension_factor_d"]
        )
        required_tlof = tlof_factor * design_diameter
        tlof_length = _positive(
            fato.get("tlof_length_m", required_tlof),
            f"Vertiport {vp_id} FATO {fato_id} tlof_length_m",
        )
        tlof_width = _positive(
            fato.get("tlof_width_m", required_tlof),
            f"Vertiport {vp_id} FATO {fato_id} tlof_width_m",
        )
        if tlof_length + 1e-9 < required_tlof or tlof_width + 1e-9 < required_tlof:
            raise ValueError(
                f"Vertiport {vp_id} FATO {fato_id} TLOF is below the "
                f"{required_tlof:.3f} m design minimum."
            )

        fatos.append(
            {
                "id": fato_id,
                "center_local": _xy(
                    fato.get("center"), f"Vertiport {vp_id} FATO {fato_id} center"
                ),
                "elevated": elevated,
                "length_m": declared_length,
                "width_m": declared_width,
                "tlof_length_m": tlof_length,
                "tlof_width_m": tlof_width,
                "safety_margin_m": safety_margin,
                "protected_radius_m": max(declared_length, declared_width) / 2.0
                + safety_margin,
            }
        )
    return fatos


def _validate_clearances(stands, fatos, vp_id):
    for index, first in enumerate(stands):
        for second in stands[index + 1 :]:
            required = (
                first["protected_diameter_m"] + second["protected_diameter_m"]
            ) / 2.0
            if distance(first["center_local"], second["center_local"]) + 1e-9 < required:
                raise ValueError(
                    f"Vertiport {vp_id} protected stand areas overlap: "
                    f"{first['id']} and {second['id']}."
                )
    for index, first in enumerate(fatos):
        for second in fatos[index + 1 :]:
            required = first["protected_radius_m"] + second["protected_radius_m"]
            if distance(first["center_local"], second["center_local"]) + 1e-9 < required:
                raise ValueError(
                    f"Vertiport {vp_id} FATO safety areas overlap: "
                    f"{first['id']} and {second['id']}."
                )
    for stand in stands:
        stand_radius = stand["protected_diameter_m"] / 2.0
        for fato in fatos:
            required = stand_radius + fato["protected_radius_m"]
            if distance(stand["center_local"], fato["center_local"]) + 1e-9 < required:
                raise ValueError(
                    f"Vertiport {vp_id} stand {stand['id']} overlaps the safety "
                    f"area of FATO {fato['id']}."
                )


def vertiport_geometry(vertiport, vehicle_type, rules):
    """
    Resolve absolute MATSim coordinates from a vertiport's local layout.

    ``x`` and ``y`` locate the terminal. Every other layout point is an [x, y]
    offset from that terminal, allowing each vertiport to have a different
    orientation and footprint without changing topology code.
    """
    vp_id = str(vertiport.get("id", "<missing>"))
    origin = _xy((vertiport.get("x"), vertiport.get("y")), f"Vertiport {vp_id}")
    layout = vertiport.get("layout")
    if not isinstance(layout, dict):
        raise ValueError(f"Vertiport {vp_id} must define a 'layout' mapping.")

    geometry = {"terminal": origin}
    for point in FIXED_LAYOUT_POINTS:
        if point not in layout:
            raise ValueError(f"Vertiport {vp_id} layout is missing '{point}'.")
        dx, dy = _xy(layout[point], f"Vertiport {vp_id} layout.{point}")
        geometry[point] = (origin[0] + dx, origin[1] + dy)

    if len(set(geometry.values())) != len(geometry):
        raise ValueError(f"Vertiport {vp_id} layout contains overlapping topology points.")

    envelope = _design_envelope(vehicle_type)
    checked_rules = _validated_rules(rules)
    stands = _stand_geometry(
        layout.get("stands"), envelope["design_diameter"], checked_rules, vp_id
    )
    fatos = _fato_geometry(
        layout.get("fatos"), envelope["design_diameter"], checked_rules, vp_id
    )
    _validate_clearances(stands, fatos, vp_id)

    for stand in stands:
        local_x, local_y = stand["center_local"]
        stand["center"] = (origin[0] + local_x, origin[1] + local_y)
    for fato in fatos:
        local_x, local_y = fato["center_local"]
        fato["center"] = (origin[0] + local_x, origin[1] + local_y)

    station_stand_id = str(vertiport.get("station_stand_id", ""))
    if station_stand_id:
        matching = [stand for stand in stands if stand["id"] == station_stand_id]
        if not matching:
            raise ValueError(
                f"Vertiport {vp_id} station_stand_id {station_stand_id!r} is unknown."
            )
        station_stand = matching[0]
    else:
        station_stand = min(
            stands, key=lambda stand: distance(stand["center"], geometry["apron"])
        )

    geometry.update(
        {
            "design_envelope": envelope,
            "design_rules": checked_rules,
            "stands": stands,
            "fatos": fatos,
            "station_stand": station_stand,
            "ground_taxi_route_width_m": (
                checked_rules["ground_taxi_route_width_factor"]
                * envelope["overall_width"]
            ),
            "air_taxi_route_width_m": (
                checked_rules["air_taxi_route_width_factor"]
                * envelope["overall_width"]
            ),
        }
    )
    return geometry


def waypoint_xy(waypoint, route_id, index):
    """Validate one absolute aerial-route waypoint."""
    return _xy(waypoint, f"Aerial route {route_id} waypoint {index}")


def distance(point_a, point_b):
    """Return planar Euclidean distance in the network coordinate system."""
    return math.hypot(point_b[0] - point_a[0], point_b[1] - point_a[1])
