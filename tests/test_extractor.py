from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from module5 import AnalyticsExtractor, ExtractionPaths, FatoMovement


NETWORK = """<?xml version="1.0"?>
<network>
  <nodes>
    <node id="origin" x="-0.13" y="51.52"/>
    <node id="pt_destination" x="0.55" y="51.37"/>
    <node id="vt_terminal_1" x="0.04" y="51.50"/>
    <node id="vt_security_1" x="0.041" y="51.50"/>
    <node id="vt_gate_1" x="0.042" y="51.50"/>
    <node id="vt_stand_1_S1" x="0.043" y="51.50"/>
    <node id="vt_apron_1" x="0.044" y="51.50"/>
    <node id="vt_fato_1_F1" x="0.045" y="51.50"/>
    <node id="vt_fato_1_F1_release" x="0.045" y="51.50"/>
    <node id="vt_airborne_dummy_1" x="0.05" y="51.49"/>
    <node id="vt_airborne_dummy_2" x="0.50" y="51.38"/>
    <node id="vt_fato_2_F1" x="0.51" y="51.38"/>
    <node id="vt_fato_2_F1_release" x="0.51" y="51.38"/>
    <node id="vt_apron_2" x="0.52" y="51.38"/>
    <node id="vt_stand_2_S1" x="0.53" y="51.38"/>
    <node id="vt_terminal_2" x="0.54" y="51.38"/>
  </nodes>
  <links>
    <link id="ground" from="origin" to="vt_terminal_1" length="1" freespeed="1" capacity="10" modes="car"/>
    <link id="pt_route" from="origin" to="pt_destination" length="1" freespeed="1" capacity="10" modes="car"/>
    <link id="link_passenger_arrival_1" from="vt_terminal_1" to="vt_security_1" length="1" freespeed="1" capacity="10" modes="walk"/>
    <link id="link_security_processing_1" from="vt_security_1" to="vt_gate_1" length="1" freespeed="1" capacity="10" modes="walk"/>
    <link id="link_gate_boarding_1" from="vt_gate_1" to="vt_stand_1_S1" length="1" freespeed="1" capacity="10" modes="walk"/>
    <link id="link_stand_apron_1" from="vt_stand_1_S1" to="vt_apron_1" length="1" freespeed="1" capacity="10" modes="uam"/>
    <link id="link_apron_fato_1_F1" from="vt_apron_1" to="vt_fato_1_F1" length="1" freespeed="1" capacity="12" modes="uam"/>
    <link id="link_fato_resource_1_F1" from="vt_fato_1_F1" to="vt_fato_1_F1_release" length="1" freespeed="1" capacity="6" modes="uam"/>
    <link id="link_fato_takeoff_1_F1" from="vt_fato_1_F1_release" to="vt_airborne_dummy_1" length="1" freespeed="1" capacity="12" modes="uam"/>
    <link id="link_airroute_test_outbound_0" from="vt_airborne_dummy_1" to="vt_airborne_dummy_2" length="1" freespeed="1" capacity="10" modes="uam"/>
    <link id="link_fato_landing_2_F1" from="vt_airborne_dummy_2" to="vt_fato_2_F1" length="1" freespeed="1" capacity="12" modes="uam"/>
    <link id="link_fato_resource_2_F1" from="vt_fato_2_F1" to="vt_fato_2_F1_release" length="1" freespeed="1" capacity="6" modes="uam"/>
    <link id="link_fato_apron_2_F1" from="vt_fato_2_F1_release" to="vt_apron_2" length="1" freespeed="1" capacity="12" modes="uam"/>
    <link id="link_apron_stand_2_S1" from="vt_apron_2" to="vt_stand_2_S1" length="1" freespeed="1" capacity="10" modes="uam"/>
  </links>
</network>
"""

EVENTS = """<?xml version="1.0"?>
<events>
  <event time="80" type="departure" person="background_car_0000001" link="ground" legMode="car"/>
  <event time="80" type="vehicle enters traffic" person="background_car_0000001" vehicle="background_car_0000001" link="ground" networkMode="car"/>
  <event time="90" type="vehicle leaves traffic" person="background_car_0000001" vehicle="background_car_0000001" link="ground" networkMode="car"/>
  <event time="90" type="arrival" person="background_car_0000001" link="ground" legMode="car"/>
  <event time="100" type="departure" person="P1" link="ground" legMode="car"/>
  <event time="100" type="vehicle enters traffic" person="P1" vehicle="P1" link="ground" networkMode="car"/>
  <event time="200" type="vehicle leaves traffic" person="P1" vehicle="P1" link="ground" networkMode="car"/>
  <event time="200" type="arrival" person="P1" link="ground" legMode="car"/>
  <event time="205" type="departure" person="P5" link="ground" legMode="walk"/>
  <event time="240" type="arrival" person="P5" link="link_passenger_arrival_1" legMode="walk"/>
  <event time="200" type="actstart" person="P1" actType="vertiport_entry"/>
  <event time="260" type="actstart" person="P1" actType="vertiport_boarding"/>
  <event time="300" type="passenger waiting" person="P1" mode="uam"/>
  <event time="330" type="passenger picked up" person="P1" vehicle="uam_vh_1" mode="uam"/>
  <event time="350" type="PersonEntersVehicle" person="uam_vh_1" vehicle="uam_vh_1"/>
  <event time="360" type="vehicle enters traffic" person="uam_vh_1" vehicle="uam_vh_1" link="link_stand_apron_1" networkMode="car"/>
  <event time="361" type="left link" vehicle="uam_vh_1" link="link_stand_apron_1"/>
  <event time="361" type="entered link" vehicle="uam_vh_1" link="link_apron_fato_1_F1"/>
  <event time="370" type="left link" vehicle="uam_vh_1" link="link_apron_fato_1_F1"/>
  <event time="370" type="entered link" vehicle="uam_vh_1" link="link_fato_resource_1_F1"/>
  <event time="371" type="left link" vehicle="uam_vh_1" link="link_fato_resource_1_F1"/>
  <event time="371" type="entered link" vehicle="uam_vh_1" link="link_fato_takeoff_1_F1"/>
  <event time="380" type="left link" vehicle="uam_vh_1" link="link_fato_takeoff_1_F1"/>
  <event time="380" type="entered link" vehicle="uam_vh_1" link="link_airroute_test_outbound_0"/>
  <event time="500" type="left link" vehicle="uam_vh_1" link="link_airroute_test_outbound_0"/>
  <event time="500" type="entered link" vehicle="uam_vh_1" link="link_fato_landing_2_F1"/>
  <event time="510" type="left link" vehicle="uam_vh_1" link="link_fato_landing_2_F1"/>
  <event time="510" type="entered link" vehicle="uam_vh_1" link="link_fato_resource_2_F1"/>
  <event time="511" type="left link" vehicle="uam_vh_1" link="link_fato_resource_2_F1"/>
  <event time="511" type="entered link" vehicle="uam_vh_1" link="link_fato_apron_2_F1"/>
  <event time="520" type="left link" vehicle="uam_vh_1" link="link_fato_apron_2_F1"/>
  <event time="520" type="entered link" vehicle="uam_vh_1" link="link_apron_stand_2_S1"/>
  <event time="530" type="vehicle leaves traffic" person="uam_vh_1" vehicle="uam_vh_1" link="link_apron_stand_2_S1"/>
  <event time="550" type="passenger dropped off" person="P1" vehicle="uam_vh_1" mode="uam"/>
  <event time="550" type="arrival" person="P1" link="link_apron_stand_2_S1" legMode="uam"/>
  <event time="110" type="departure" person="P2" link="ground" legMode="car"/>
  <event time="600" type="arrival" person="P2" link="ground" legMode="car"/>
  <event time="120" type="departure" person="P3" link="pt_route" legMode="pt"/>
  <event time="125" type="TransitDriverStarts" driverId="pt_driver_1" vehicleId="bus_1" transitLineId="bus_101" transitRouteId="outbound" departureId="dep_1"/>
  <event time="127" type="PersonEntersVehicle" person="P3" vehicle="bus_1"/>
  <event time="130" type="vehicle enters traffic" person="pt_driver_1" vehicle="bus_1" link="pt_route" networkMode="car"/>
  <event time="140" type="TransitDriverStarts" driverId="pt_driver_2" vehicleId="train_1" transitLineId="rail_1" transitRouteId="outbound" departureId="dep_2"/>
  <event time="145" type="PersonEntersVehicle" person="P4" vehicle="train_1"/>
  <event time="150" type="vehicle enters traffic" person="pt_driver_2" vehicle="train_1" link="pt_route" networkMode="car"/>
  <event time="300" type="vehicle leaves traffic" person="pt_driver_2" vehicle="train_1" link="pt_route" networkMode="car"/>
  <event time="301" type="PersonLeavesVehicle" person="P4" vehicle="train_1"/>
  <event time="450" type="vehicle leaves traffic" person="pt_driver_1" vehicle="bus_1" link="pt_route" networkMode="car"/>
  <event time="450" type="PersonLeavesVehicle" person="P3" vehicle="bus_1"/>
  <event time="460" type="arrival" person="P3" link="pt_route" legMode="pt"/>
</events>
"""

POPULATION = """<?xml version="1.0"?>
<population>
  <person id="P1"><attributes><attribute name="subpopulation">high_urgency</attribute></attributes><plan><leg mode="uam"/></plan></person>
  <person id="P2"><attributes><attribute name="subpopulation">low_urgency</attribute></attributes><plan><leg mode="uam"/></plan></person>
  <person id="P3"><attributes><attribute name="subpopulation">low_urgency</attribute></attributes><plan><leg mode="uam"/></plan></person>
  <person id="background_car_0000001"><attributes><attribute name="subpopulation">default</attribute><attribute name="backgroundTraffic">true</attribute></attributes><plan><leg mode="car"/></plan></person>
</population>
"""


class ExtractorTest(unittest.TestCase):
    def test_real_metrics_are_derived_from_events(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "events.xml").write_text(EVENTS, encoding="utf-8")
            (root / "network.xml").write_text(NETWORK, encoding="utf-8")
            (root / "population.xml").write_text(POPULATION, encoding="utf-8")
            report = {
                "vertiports": [
                    {
                        "id": "1",
                        "stand_count": 1,
                        "station_stand_id": "S1",
                        "fato_count": 1,
                        "t_sep_s": 600,
                        "aggregate_fato_capacity_veh_h": 6,
                        "ground_taxi_route_width_m": 22.5,
                        "air_taxi_route_width_m": 30,
                        "stands": [
                            {
                                "id": "S1",
                                "center": [0.043, 51.50],
                                "dimension_m": 18,
                                "protection_margin_m": 6,
                            }
                        ],
                        "fatos": [
                            {
                                "id": "F1",
                                "center": [0.045, 51.50],
                                "elevated": False,
                                "length_m": 22.5,
                                "width_m": 22.5,
                                "tlof_length_m": 12.45,
                                "tlof_width_m": 12.45,
                                "safety_margin_m": 3.75,
                            }
                        ],
                    },
                    {
                        "id": "2",
                        "stand_count": 1,
                        "station_stand_id": "S1",
                        "fato_count": 1,
                        "t_sep_s": 600,
                        "aggregate_fato_capacity_veh_h": 6,
                        "ground_taxi_route_width_m": 22.5,
                        "air_taxi_route_width_m": 30,
                        "stands": [],
                        "fatos": [
                            {
                                "id": "F1",
                                "center": [0.51, 51.38],
                                "elevated": False,
                                "length_m": 22.5,
                                "width_m": 22.5,
                                "tlof_length_m": 12.45,
                                "tlof_width_m": 12.45,
                                "safety_margin_m": 3.75,
                            }
                        ],
                    },
                ]
            }
            (root / "design.json").write_text(json.dumps(report), encoding="utf-8")
            paths = ExtractionPaths(
                events=root / "events.xml",
                network=root / "network.xml",
                design_report=root / "design.json",
                population=root / "population.xml",
                output_dir=root / "analytics",
                background_traffic_enabled=True,
            )

            extractor = AnalyticsExtractor(paths, crs="EPSG:4326")
            bundle_path = extractor.extract(force=True)
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

            self.assertEqual(bundle["schemaVersion"], 8)
            self.assertTrue(bundle["run"]["backgroundTrafficEnabled"])
            self.assertNotIn("resilience", bundle)
            self.assertEqual(bundle["outcomes"]["eligibleTravellers"], 3)
            self.assertEqual(bundle["outcomes"]["uamCompleted"], 1)
            self.assertEqual(bundle["outcomes"]["carSelected"], 1)
            self.assertEqual(bundle["outcomes"]["ptSelected"], 1)
            self.assertEqual(bundle["outcomes"]["unobserved"], 0)
            self.assertEqual(bundle["outcomes"]["abandonmentRate"], 0.6667)
            self.assertEqual(
                {
                    journey["personId"]: journey["outcome"]
                    for journey in bundle["journeys"]
                },
                {"P1": "uam", "P2": "car", "P3": "pt"},
            )
            self.assertEqual(bundle["waitTimes"][0]["waitSeconds"], 30)
            self.assertEqual(
                {trajectory["mode"] for trajectory in bundle["trajectories"]},
                {"walk", "car", "bus", "train", "uam"},
            )
            background = [
                trajectory
                for trajectory in bundle["trajectories"]
                if trajectory["isBackground"]
            ]
            self.assertEqual(len(background), 1)
            self.assertEqual(background[0]["vehicleId"], "background_car_0000001")
            self.assertEqual(bundle["run"]["startTime"], 80)
            peak_occupancy = {
                trajectory["mode"]: max(
                    sample["count"] for sample in trajectory["occupancy"]
                )
                for trajectory in bundle["trajectories"]
            }
            self.assertEqual(
                peak_occupancy,
                {"walk": 0, "car": 1, "bus": 1, "train": 1, "uam": 1},
            )
            walk = next(
                trajectory
                for trajectory in bundle["trajectories"]
                if trajectory["mode"] == "walk"
            )
            self.assertEqual(walk["vehicleId"], "P5")
            self.assertEqual(walk["timestamps"][0], 205.0)
            self.assertEqual(walk["timestamps"][-1], 240.0)
            self.assertGreaterEqual(len(walk["path"]), 3)
            self.assertEqual(bundle["capacity"]["movementCount"], 2)
            fato_occupancy = {
                facility["vertiportId"]: max(
                    sample["occupancy"] for sample in facility["series"]
                )
                for facility in bundle["fatoOccupancyByVertiport"]
            }
            self.assertEqual(fato_occupancy, {"1": 1, "2": 1})
            self.assertEqual(bundle["capacity"]["headwayComparisonCount"], 0)
            self.assertEqual(bundle["capacity"]["headwayViolationCount"], 0)
            self.assertEqual(len(bundle["capacity"]["byFato"]), 2)
            self.assertEqual(len(bundle["vertiports"]), 2)

            capacity = extractor._build_capacity(
                [
                    FatoMovement(100, "1", "F1", "uam_1", "takeoff"),
                    FatoMovement(700, "1", "F1", "uam_2", "landing"),
                    FatoMovement(1200, "1", "F1", "uam_3", "takeoff"),
                ],
                0,
                1200,
            )
            self.assertEqual(capacity["headwayComparisonCount"], 2)
            self.assertEqual(capacity["headwayViolationCount"], 1)
            self.assertEqual(capacity["minimumObservedSeparationSeconds"], 500)
            self.assertEqual(
                [sample["compliant"] for sample in capacity["headwaySeries"]],
                [True, False],
            )

            disabled_paths = ExtractionPaths(
                events=root / "events.xml",
                network=root / "network.xml",
                design_report=root / "design.json",
                population=root / "population.xml",
                output_dir=root / "analytics_without_background_traffic",
                background_traffic_enabled=False,
            )
            disabled_bundle_path = AnalyticsExtractor(
                disabled_paths, crs="EPSG:4326"
            ).extract(force=True)
            disabled_bundle = json.loads(
                disabled_bundle_path.read_text(encoding="utf-8")
            )
            self.assertFalse(disabled_bundle["run"]["backgroundTrafficEnabled"])
            self.assertFalse(
                any(
                    trajectory["isBackground"]
                    for trajectory in disabled_bundle["trajectories"]
                )
            )
            self.assertNotEqual(
                bundle["run"]["sourceSignature"],
                disabled_bundle["run"]["sourceSignature"],
            )


if __name__ == "__main__":
    unittest.main()
