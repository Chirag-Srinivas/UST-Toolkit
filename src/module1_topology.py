# module1_topology.py - Micro-Topology Generation based on EASA/SORA constraints
import config
import json
import math
import os
import re
import xml.etree.ElementTree as ET
import networkx as nx
from uam_geometry import distance, vertiport_geometry, waypoint_xy
from xml_writer import merge_matsim_network


# QSim advances and emits events on integer-second boundaries.  A one-second
# conservative guard prevents a nominal 600-second link-flow headway from
# appearing as alternating 600/599-second releases because of inclusive time
# steps.  The design report and dashboard still use the exact configured
# t_sep; this guard applies only to the generated enforcement link.
FATO_FLOW_TIME_STEP_GUARD_S = 1.0

class TopologyBuilder:
    """
    Constructs the micro-topology for UAM vertiports and demand hubs.
    Operates under the assumption that the base network is pre-cleaned 
    by MATSim's native NetworkCleaner to prevent topological islands.
    """
    def __init__(self):
        # Safely extract configuration variables
        self.vertiports = getattr(config, 'VERTIPORTS', [])
        self.demand_events = getattr(config, 'DEMAND_EVENTS', [])
        self.aerial_routes = getattr(config, 'AERIAL_ROUTES', [])
        self.vehicle_type = getattr(config, 'UAM_VEHICLE_TYPE', {})
        self.design_rules = getattr(config, 'VERTIPORT_DESIGN_RULES', {})
        
        # Caching variables for network graph to prevent O(N^2) redundancy
        self._cached_lscc = None
        self._cached_node_coords = None

    def _build_and_cache_lscc(self, base_network_path, allowed_modes):
        """
        Internal method to parse the XML, build a directed graph, 
        and cache the Largest Strongly Connected Component (LSCC).
        """
        print("[TopologyBuilder] Initialising directed graph for SCC analysis...")
        tree = ET.parse(base_network_path)
        root = tree.getroot()
        
        G = nx.DiGraph()
        self._cached_node_coords = {}
        
        # Map all node coordinates
        for node in root.findall(".//node"):
            node_id = node.get("id")
            self._cached_node_coords[node_id] = (float(node.get("x")), float(node.get("y")))
            
        # Add valid edges to the directed graph
        for link in root.findall(".//link"):
            modes_attr = link.get("modes", "car") 
            capacity = float(link.get("capacity", 0.0))
            freespeed = float(link.get("freespeed", 0.0))
            
            link_modes = set(m.strip() for m in modes_attr.split(","))
            
            # Bypass OSM garbage data (driveways, alleys, mis-tagged paths)
            if "car" in allowed_modes:
                # Must be a major road: >= 500 vehicles/hr and >= ~29 km/h speed limit
                if "car" in link_modes and capacity >= 500.0 and freespeed >= 8.0:
                    G.add_edge(link.get("from"), link.get("to"))
            else:
                if link_modes.intersection(allowed_modes):
                    G.add_edge(link.get("from"), link.get("to"))
                    
        # Compute Strongly Connected Components
        scc_generator = nx.strongly_connected_components(G)
        scc_list = list(scc_generator)
        
        if not scc_list:
            raise RuntimeError("CRITICAL ERROR: No valid routing components found in the network.")
            
        # Extract the largest component
        self._cached_lscc = set(max(scc_list, key=len))
        print(f"[TopologyBuilder] LSCC established. Contains {len(self._cached_lscc)} highly routable nodes.")

    def find_nearest_base_node(self, base_network_path, x, y, allowed_modes={"car"}, search_radius=150.0):
        """
        Performs a spatial Euclidean search to snap coordinates to the closest node 
        within a specified radius, strictly constrained to the Largest Strongly Connected Component.
        """
        print(f"[TopologyBuilder] Scanning for anchor coordinates ({x}, {y}) within {search_radius}m...")
        
        if not os.path.exists(base_network_path):
            raise FileNotFoundError(f"Base network file not found at: {base_network_path}")
            
        # Build graph cache on first call to save memory/processing time
        if self._cached_lscc is None or self._cached_node_coords is None:
            self._build_and_cache_lscc(base_network_path, allowed_modes)
                
        candidates = []
        
        # 1. Find all candidate nodes within the radius that are in the LSCC
        for node_id in self._cached_lscc:
            # Ensure the node has coordinate data
            if node_id in self._cached_node_coords:
                nx_coord, ny_coord = self._cached_node_coords[node_id]
                
                # Euclidean distance calculation
                dist = math.sqrt((nx_coord - x)**2 + (ny_coord - y)**2)
                
                if dist <= search_radius:
                    candidates.append((dist, node_id))
                    
        # 2. Validation check
        if not candidates:
            raise ValueError(
                f"No strongly connected '{allowed_modes}' nodes found within {search_radius}m "
                f"of coordinates ({x}, {y}). Check vertiport placement or increase search radius."
            )
            
        # 3. Sort by distance and isolate the closest
        candidates.sort(key=lambda item: item[0])
        best_dist, best_node_id = candidates[0]
        
        print(f"[TopologyBuilder] Successfully snapped to SCC Base Node ID: '{best_node_id}' (Distance: {best_dist:.2f}m)")
        return best_node_id

    @staticmethod
    def _route_token(route_id):
        """Return a MATSim-safe route identifier without silently renaming it."""
        route_id = str(route_id)
        if not route_id or re.fullmatch(r"[A-Za-z0-9_.-]+", route_id) is None:
            raise ValueError(
                f"Invalid aerial route id {route_id!r}; use letters, numbers, '.', '_' or '-'."
            )
        return route_id

    @staticmethod
    def _append_route_links(all_links, route_id, nodes, freespeed, capacity, direction):
        """Append one directed polyline as consecutive MATSim links."""
        for index, ((from_node, from_xy), (to_node, to_xy)) in enumerate(zip(nodes, nodes[1:])):
            segment_length = distance(from_xy, to_xy)
            if segment_length <= 0.0:
                raise ValueError(
                    f"Aerial route {route_id} has a zero-length segment at index {index}."
                )
            all_links.append({
                "id": f"link_airroute_{route_id}_{direction}_{index}",
                "from": from_node,
                "to": to_node,
                "length": segment_length,
                "freespeed": freespeed,
                "capacity": capacity,
                "modes": "uam",
            })

    def _build_aerial_routes(self, all_nodes, all_links, vertiport_geometries):
        """Build configured waypoint polylines between vertiport airborne nodes."""
        if len(vertiport_geometries) >= 2 and not self.aerial_routes:
            raise ValueError("At least one AERIAL_ROUTES entry is required for multiple vertiports.")

        known_route_ids = set()
        default_speed = float(self.vehicle_type.get("cruise_speed", 55.5))
        for route in self.aerial_routes:
            if not isinstance(route, dict):
                raise ValueError("Every AERIAL_ROUTES entry must be a mapping.")

            route_id = self._route_token(route.get("id", ""))
            if route_id in known_route_ids:
                raise ValueError(f"Duplicate aerial route id: {route_id}")
            known_route_ids.add(route_id)

            from_id = str(route.get("from_vertiport", ""))
            to_id = str(route.get("to_vertiport", ""))
            if from_id == to_id:
                raise ValueError(f"Aerial route {route_id} must connect two different vertiports.")
            if from_id not in vertiport_geometries or to_id not in vertiport_geometries:
                raise ValueError(
                    f"Aerial route {route_id} references unknown vertiports {from_id!r} -> {to_id!r}."
                )

            freespeed = float(route.get("freespeed", default_speed))
            capacity = float(route.get("capacity", 999999.0))
            if freespeed <= 0.0 or capacity <= 0.0:
                raise ValueError(
                    f"Aerial route {route_id} requires positive freespeed and capacity."
                )

            route_nodes = [
                (f"vt_airborne_dummy_{from_id}", vertiport_geometries[from_id]["airborne"])
            ]
            for index, waypoint in enumerate(route.get("waypoints", [])):
                waypoint_id = f"airroute_{route_id}_waypoint_{index}"
                waypoint_coord = waypoint_xy(waypoint, route_id, index)
                all_nodes.append({"id": waypoint_id, "x": waypoint_coord[0], "y": waypoint_coord[1]})
                route_nodes.append((waypoint_id, waypoint_coord))
            route_nodes.append(
                (f"vt_airborne_dummy_{to_id}", vertiport_geometries[to_id]["airborne"])
            )

            self._append_route_links(
                all_links, route_id, route_nodes, freespeed, capacity, "outbound"
            )
            if bool(route.get("bidirectional", False)):
                self._append_route_links(
                    all_links,
                    route_id,
                    list(reversed(route_nodes)),
                    freespeed,
                    capacity,
                    "return",
                )

    def _write_vertiport_design_report(self, output_dir, vertiport_geometries):
        """Write a reproducible record of derived prototype-design dimensions."""
        envelope = next(iter(vertiport_geometries.values()))["design_envelope"]
        report = {
            "status": "prototype geometry checks passed",
            "regulatory_status": (
                "Research-simulation implementation of EASA PTS-VPT-DSN "
                "(March 2022); not a certification or construction approval."
            ),
            "implemented_scope": [
                "design-aircraft D envelope",
                "FATO and TLOF minimum dimensions",
                "FATO safety-area margin",
                "stand and stand-protection dimensions",
                "ground/air taxi-route width metadata",
                "independent FATO resources and t_sep throughput",
            ],
            "excluded_scope": [
                "obstacle survey and obstacle-free volume assessment",
                "visual aids, markings and lighting",
                "rescue and firefighting provision",
                "pavement strength, drainage and structural design",
                "downwash/outwash hazard assessment",
                "noise, environmental and planning approval",
            ],
            "design_vehicle": {
                "id": str(self.vehicle_type.get("id", "")),
                **envelope,
            },
            "vertiports": [],
        }
        vertiports_by_id = {str(vp["id"]): vp for vp in self.vertiports}
        for vp_id, geometry in vertiport_geometries.items():
            vp = vertiports_by_id[vp_id]
            t_sep = float(vp["t_sep"])
            report["vertiports"].append(
                {
                    "id": vp_id,
                    "stand_count": len(geometry["stands"]),
                    "station_stand_id": geometry["station_stand"]["id"],
                    "fato_count": len(geometry["fatos"]),
                    "t_sep_s": t_sep,
                    "aggregate_fato_capacity_veh_h": len(geometry["fatos"])
                    * 3600.0
                    / t_sep,
                    "capacity_enforcement": "shared_fato_bottleneck_link",
                    "capacity_enforcement_time_step_guard_s": (
                        FATO_FLOW_TIME_STEP_GUARD_S
                    ),
                    "enforced_fato_link_capacity_veh_h": (
                        len(geometry["fatos"])
                        * 3600.0
                        / (t_sep + FATO_FLOW_TIME_STEP_GUARD_S)
                    ),
                    "ground_taxi_route_width_m": geometry[
                        "ground_taxi_route_width_m"
                    ],
                    "air_taxi_route_width_m": geometry["air_taxi_route_width_m"],
                    "stands": [
                        {
                            "id": stand["id"],
                            "center": list(stand["center"]),
                            "dimension_m": stand["dimension_m"],
                            "protection_margin_m": stand["protection_margin_m"],
                        }
                        for stand in geometry["stands"]
                    ],
                    "fatos": [
                        {
                            "id": fato["id"],
                            "center": list(fato["center"]),
                            "elevated": fato["elevated"],
                            "length_m": fato["length_m"],
                            "width_m": fato["width_m"],
                            "tlof_length_m": fato["tlof_length_m"],
                            "tlof_width_m": fato["tlof_width_m"],
                            "safety_margin_m": fato["safety_margin_m"],
                        }
                        for fato in geometry["fatos"]
                    ],
                }
            )
        report_path = os.path.join(output_dir, "vertiport_design_report.json")
        with open(report_path, "w", encoding="utf-8") as report_file:
            json.dump(report, report_file, indent=2)
        print(f"[TopologyBuilder] Prototype-design report saved to: {report_path}")

    def build_network(self, output_dir="../scenarios/networks", base_network_path=None):
        print("--- Module 1: TopologyBuilder Initiated ---")
        if base_network_path is None:
            base_network_path = getattr(config, 'BASE_NETWORK_PATH', '../data/base_network.xml')
            
        all_nodes = []
        all_links = []
        vertiport_geometries = {}

        # Keep road vehicles out of passenger-processing and apron links. The
        # explicit car trip ends at the road-side vertiport interface.
        road_modes = "walk,car,pt,access_uam_car,egress_uam_car"
        passenger_entry_modes = "walk"
        passenger_egress_modes = "walk"
        station_modes = "walk,uam"

        # =====================================================================
        # 1. DYNAMIC ORIGIN & DESTINATION HUB GENERATION
        # =====================================================================
        for idx, event in enumerate(self.demand_events):
            hx, hy = float(event["origin_x"]), float(event["origin_y"])
            print(f"\nProcessing Demand Event {idx} Origin: ({hx}, {hy})")
            nearest_origin = self.find_nearest_base_node(base_network_path, hx, hy, allowed_modes={"car"})
            
            if nearest_origin:
                all_nodes.append({"id": f"origin_node_{idx}", "x": hx, "y": hy})
                all_links.extend([
                    {"id": f"link_origin_egress_{idx}", "from": f"origin_node_{idx}", "to": str(nearest_origin), "length": 50.0, "freespeed": 13.8, "capacity": 5000, "modes": road_modes},
                    {"id": f"link_origin_access_{idx}", "from": str(nearest_origin), "to": f"origin_node_{idx}", "length": 50.0, "freespeed": 13.8, "capacity": 5000, "modes": road_modes}
                ])
                
            dx, dy = float(event["dest_x"]), float(event["dest_y"])
            print(f"Processing Demand Event {idx} Destination: ({dx}, {dy})")
            nearest_dest = self.find_nearest_base_node(base_network_path, dx, dy, allowed_modes={"car"})
            
            if nearest_dest:
                all_nodes.append({"id": f"dest_node_{idx}", "x": dx, "y": dy})
                all_links.extend([
                    {"id": f"link_dest_access_{idx}", "from": str(nearest_dest), "to": f"dest_node_{idx}", "length": 50.0, "freespeed": 13.8, "capacity": 5000, "modes": road_modes},
                    {"id": f"link_dest_egress_{idx}", "from": f"dest_node_{idx}", "to": str(nearest_dest), "length": 50.0, "freespeed": 13.8, "capacity": 5000, "modes": road_modes}
                ])

        # =====================================================================
        # 2. VERTIPORT MICRO-SUBGRAPH GENERATION
        # =====================================================================
        for vp in self.vertiports:
            if not isinstance(vp, dict): continue
            vp_id = str(vp["id"])
            vp_x, vp_y = float(vp["x"]), float(vp["y"])
            print(f"\nProcessing Vertiport: {vp_id}")
            
            if vp_id in vertiport_geometries:
                raise ValueError(f"Duplicate vertiport id: {vp_id}")
            geometry = vertiport_geometry(vp, self.vehicle_type, self.design_rules)
            vertiport_geometries[vp_id] = geometry

            t_sep = float(vp.get("t_sep", 600.0))
            if t_sep <= 0.0:
                raise ValueError(
                    f"Vertiport {vp_id} has invalid t_sep={t_sep}; "
                    "separation time must be greater than zero seconds."
                )
            fato_count = len(geometry["fatos"])
            per_fato_capacity = 3600.0 / t_sep
            enforced_per_fato_capacity = 3600.0 / (
                t_sep + FATO_FLOW_TIME_STEP_GUARD_S
            )
            # Aggregate independent FATO throughput in vehicles per hour.
            fato_capacity = fato_count * per_fato_capacity
            # Keep the apron above the FATO rate so the FATO headway is the
            # intentional controlling constraint.
            apron_capacity = fato_capacity * 2.0
            nearest_base_node_id = self.find_nearest_base_node(base_network_path, vp_x, vp_y, allowed_modes={"car"})

            all_nodes.extend([
                {"id": f"vt_terminal_{vp_id}", "x": geometry["terminal"][0], "y": geometry["terminal"][1]},
                {"id": f"vt_security_{vp_id}", "x": geometry["security"][0], "y": geometry["security"][1]},
                {"id": f"vt_gate_{vp_id}", "x": geometry["gate"][0], "y": geometry["gate"][1]},
                {"id": f"vt_apron_{vp_id}", "x": geometry["apron"][0], "y": geometry["apron"][1]},
                {"id": f"vt_airborne_dummy_{vp_id}", "x": geometry["airborne"][0], "y": geometry["airborne"][1]},
            ])
            for stand in geometry["stands"]:
                all_nodes.append(
                    {
                        "id": f"vt_stand_{vp_id}_{stand['id']}",
                        "x": stand["center"][0],
                        "y": stand["center"][1],
                    }
                )
            for fato in geometry["fatos"]:
                all_nodes.append(
                    {
                        "id": f"vt_fato_{vp_id}_{fato['id']}",
                        "x": fato["center"][0],
                        "y": fato["center"][1],
                    }
                )
                # Take-offs and landings must share one physical FATO
                # throughput resource.  Both directions merge at the FATO
                # node, traverse this logical release node in the same
                # direction, and only then branch towards the apron or the
                # airborne network.  This prevents MATSim from applying the
                # configured movement rate independently to arrival and
                # departure links.
                all_nodes.append(
                    {
                        "id": f"vt_fato_{vp_id}_{fato['id']}_release",
                        "x": fato["center"][0],
                        "y": fato["center"][1],
                    }
                )

            terminal_security_length = distance(geometry["terminal"], geometry["security"])
            security_gate_length = distance(geometry["security"], geometry["gate"])
            station_stand = geometry["station_stand"]
            station_stand_node = f"vt_stand_{vp_id}_{station_stand['id']}"
            gate_stand_length = distance(geometry["gate"], station_stand["center"])
            stand_terminal_length = distance(
                station_stand["center"], geometry["terminal"]
            )

            # These links represent physical passenger movement only.  The
            # configured t_process is deliberately excluded here and is
            # represented exactly once by the MATSim-UAM station's pre-flight
            # interaction activity.  The legacy security-processing link ID is
            # retained for compatibility, but it now uses normal walking speed.
            # Station/apron links remain reserved for passengers and UAM
            # vehicles, and all physical stands and FATOs are separate
            # topology resources.
            all_links.extend([
                {"id": f"link_passenger_arrival_{vp_id}", "from": f"vt_terminal_{vp_id}", "to": f"vt_security_{vp_id}", "length": terminal_security_length, "freespeed": 1.34, "capacity": 999999.0, "modes": passenger_entry_modes},
                {"id": f"link_security_processing_{vp_id}", "from": f"vt_security_{vp_id}", "to": f"vt_gate_{vp_id}", "length": security_gate_length, "freespeed": 1.34, "capacity": 999999.0, "modes": passenger_entry_modes},
                {"id": f"link_gate_boarding_{vp_id}", "from": f"vt_gate_{vp_id}", "to": station_stand_node, "length": gate_stand_length, "freespeed": 1.0, "capacity": 999999.0, "modes": passenger_entry_modes},
                {"id": f"link_passenger_egress_{vp_id}", "from": station_stand_node, "to": f"vt_terminal_{vp_id}", "length": stand_terminal_length, "freespeed": 1.34, "capacity": 999999.0, "modes": passenger_egress_modes},
            ])

            for stand in geometry["stands"]:
                stand_node = f"vt_stand_{vp_id}_{stand['id']}"
                stand_apron_length = distance(stand["center"], geometry["apron"])
                outbound_id = (
                    f"link_stand_apron_{vp_id}"
                    if stand["id"] == station_stand["id"]
                    else f"link_stand_apron_{vp_id}_{stand['id']}"
                )
                all_links.extend(
                    [
                        {
                            "id": outbound_id,
                            "from": stand_node,
                            "to": f"vt_apron_{vp_id}",
                            "length": stand_apron_length,
                            "freespeed": 5.0,
                            "capacity": apron_capacity,
                            "modes": station_modes,
                        },
                        {
                            "id": f"link_apron_stand_{vp_id}_{stand['id']}",
                            "from": f"vt_apron_{vp_id}",
                            "to": stand_node,
                            "length": stand_apron_length,
                            "freespeed": 5.0,
                            "capacity": apron_capacity,
                            "modes": station_modes,
                        },
                    ]
                )

            for fato in geometry["fatos"]:
                fato_node = f"vt_fato_{vp_id}_{fato['id']}"
                fato_release_node = f"{fato_node}_release"
                apron_fato_length = distance(geometry["apron"], fato["center"])
                fato_airborne_length = distance(fato["center"], geometry["airborne"])
                all_links.extend(
                    [
                        {
                            "id": f"link_apron_fato_{vp_id}_{fato['id']}",
                            "from": f"vt_apron_{vp_id}",
                            "to": fato_node,
                            "length": apron_fato_length,
                            "freespeed": 5.0,
                            "capacity": apron_capacity,
                            "modes": "uam",
                        },
                        {
                            "id": f"link_fato_landing_{vp_id}_{fato['id']}",
                            "from": f"vt_airborne_dummy_{vp_id}",
                            "to": fato_node,
                            "length": fato_airborne_length,
                            "freespeed": float(
                                self.vehicle_type.get("vertical_speed", 5.0)
                            ),
                            "capacity": apron_capacity,
                            "modes": "uam",
                        },
                        {
                            # The only per-FATO link carrying the t_sep-derived
                            # flow capacity.  Every arrival and departure must
                            # traverse it, so its outflow is the shared movement
                            # stream for this physical FATO.
                            "id": f"link_fato_resource_{vp_id}_{fato['id']}",
                            "from": fato_node,
                            "to": fato_release_node,
                            "length": 1.0,
                            "freespeed": 1.0,
                            "capacity": enforced_per_fato_capacity,
                            "modes": "uam",
                        },
                        {
                            "id": f"link_fato_takeoff_{vp_id}_{fato['id']}",
                            "from": fato_release_node,
                            "to": f"vt_airborne_dummy_{vp_id}",
                            "length": fato_airborne_length,
                            "freespeed": float(
                                self.vehicle_type.get("vertical_speed", 5.0)
                            ),
                            "capacity": apron_capacity,
                            "modes": "uam",
                        },
                        {
                            "id": f"link_fato_apron_{vp_id}_{fato['id']}",
                            "from": fato_release_node,
                            "to": f"vt_apron_{vp_id}",
                            "length": apron_fato_length,
                            "freespeed": 5.0,
                            "capacity": apron_capacity,
                            "modes": "uam",
                        },
                    ]
                )

            if nearest_base_node_id:
                all_links.extend([
                    {"id": f"link_base_to_vt_interface_{vp_id}", "from": str(nearest_base_node_id), "to": f"vt_terminal_{vp_id}", "length": 5000.0, "freespeed": 13.8, "capacity": 999999, "modes": road_modes},
                    {"id": f"link_vt_to_base_interface_{vp_id}", "from": f"vt_terminal_{vp_id}", "to": str(nearest_base_node_id), "length": 50.0, "freespeed": 13.8, "capacity": 2000, "modes": road_modes}
                ])

        # =====================================================================
        # 3. CONFIGURED AERIAL ROUTE GENERATION
        # =====================================================================
        self._build_aerial_routes(all_nodes, all_links, vertiport_geometries)

        # =====================================================================
        # 4. NETWORK EXPORT
        # =====================================================================
        os.makedirs(output_dir, exist_ok=True)
        output_file = f"{output_dir}/network_micro.xml"
        print(f"\n[TopologyBuilder] Merging micro-topology variables into base network: {base_network_path}")
        
        merge_matsim_network(
            base_network_path=base_network_path, 
            nodes_list=all_nodes, 
            links_list=all_links, 
            output_path=output_file
        )
        self._write_vertiport_design_report(output_dir, vertiport_geometries)
        print(f"[TopologyBuilder] Complete. Final micro-network configuration saved to: {output_file}")

if __name__ == "__main__":
    builder = TopologyBuilder()
    builder.build_network()
