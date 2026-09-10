from __future__ import annotations

import copy
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import networkx as nx

import config
from module1_topology import FATO_FLOW_TIME_STEP_GUARD_S, TopologyBuilder


class FatoTopologyTest(unittest.TestCase):
    def test_arrivals_and_departures_share_one_capacity_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vertiport = json.loads((Path(__file__).parent / "fixtures" / "vertiport.json").read_text())
            x = float(vertiport["x"])
            y = float(vertiport["y"])
            base_network = root / "base_network.xml"
            base_network.write_text(
                f"""<?xml version="1.0"?>
<network>
  <nodes>
    <node id="road_1" x="{x}" y="{y}"/>
    <node id="road_2" x="{x + 10}" y="{y}"/>
  </nodes>
  <links>
    <link id="road_out" from="road_1" to="road_2" length="10" freespeed="13.8" capacity="1000" modes="car"/>
    <link id="road_back" from="road_2" to="road_1" length="10" freespeed="13.8" capacity="1000" modes="car"/>
  </links>
</network>
""",
                encoding="utf-8",
            )

            builder = TopologyBuilder()
            builder.vertiports = [vertiport]
            builder.demand_events = []
            builder.aerial_routes = []
            builder.build_network(
                output_dir=str(root), base_network_path=str(base_network)
            )

            network_root = ET.parse(root / "network_micro.xml").getroot()
            links = {
                link.attrib["id"]: link.attrib
                for link in network_root.findall("./links/link")
            }
            resource_id = "link_fato_resource_1_F1"
            self.assertIn(resource_id, links)
            expected_enforcement_capacity = 3600.0 / (
                600.0 + FATO_FLOW_TIME_STEP_GUARD_S
            )
            self.assertAlmostEqual(
                float(links[resource_id]["capacity"]),
                expected_enforcement_capacity,
            )

            for feeder_id in (
                "link_apron_fato_1_F1",
                "link_fato_landing_1_F1",
                "link_fato_takeoff_1_F1",
                "link_fato_apron_1_F1",
            ):
                self.assertGreater(
                    float(links[feeder_id]["capacity"]),
                    float(links[resource_id]["capacity"]),
                )

            graph = nx.DiGraph()
            for link_id, attributes in links.items():
                if "uam" in attributes.get("modes", "").split(","):
                    graph.add_edge(
                        attributes["from"], attributes["to"], link_id=link_id
                    )

            for origin, destination in (
                ("vt_apron_1", "vt_airborne_dummy_1"),
                ("vt_airborne_dummy_1", "vt_apron_1"),
            ):
                nodes = nx.shortest_path(graph, origin, destination)
                path_links = [
                    graph.edges[start, end]["link_id"]
                    for start, end in zip(nodes, nodes[1:])
                ]
                self.assertIn(resource_id, path_links)

            report = json.loads(
                (root / "vertiport_design_report.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                report["vertiports"][0]["capacity_enforcement"],
                "shared_fato_bottleneck_link",
            )
            self.assertEqual(
                report["vertiports"][0][
                    "capacity_enforcement_time_step_guard_s"
                ],
                1.0,
            )
            self.assertEqual(
                report["vertiports"][0]["aggregate_fato_capacity_veh_h"],
                6.0,
            )


if __name__ == "__main__":
    unittest.main()
