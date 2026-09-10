import copy
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import config
import pipeline
from module2_demand import DemandGenerator
from module3_transport import TransportSupplyGenerator, normalise_transport_config


class OptionalTransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        vp = json.loads((Path(__file__).parent / "fixtures/vertiport.json").read_text())
        vp["layout"]["stands"]["count"] = 2
        second = copy.deepcopy(vp)
        second.update(id="2", x=1000.0)
        network = self.root / "network.xml"
        network.write_text('<network><nodes><node id="a" x="0" y="0"/><node id="b" x="1000" y="0"/></nodes><links><link id="ab" from="a" to="b" length="1000" freespeed="15" capacity="1800" permlanes="1" modes="car"/></links></network>')
        jar = self.root / "runtime.jar"
        jar.write_bytes(b"preflight-existence-check-only")
        self.event = dict(source_name="synthetic", origin_x=0, origin_y=0,
                          dest_x=1000, dest_y=0, vertiport_id="1", dest_vertiport_id="2",
                          t_event=28800, c_source=2, uam_adoption=1,
                          release_delay_mean_s=0, release_delay_std_s=0,
                          high_urgency_ratio=0.5)
        self.settings = dict(SCENARIO_NAME="optional_transport_test", VERTIPORTS=[vp, second],
                             FLEET_SIZE=4, BASE_NETWORK_PATH=str(network), MATSIM_JAR_PATH=str(jar),
                             BASE_POPULATION_PATH="", MODULE5_CRS="EPSG:27700",
                             AERIAL_ROUTES=[dict(from_vertiport="1", to_vertiport="2")],
                             DEMAND_EVENTS=[self.event],
                             TRANSPORT_SUPPLY=dict(enabled=True, trains=[], buses=[]))
        self.config_patch = patch.dict(config.__dict__, self.settings)
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)

    def test_empty_and_disabled_supply_preserve_network_and_write_uam_fleet(self):
        for raw in (dict(enabled=True, trains=[], buses=[]), dict(enabled=False),
                    dict(enabled=False, network={"strategy": "pseudo_network"}, services=[{"stale": True}])):
            with self.subTest(raw=raw):
                before = Path(config.BASE_NETWORK_PATH).read_bytes()
                paths = TransportSupplyGenerator(raw).generate(
                    base_network=Path(config.BASE_NETWORK_PATH),
                    network_output=self.root / "unused.xml", output_directory=self.root / "supply")
                self.assertEqual(paths.network, Path(config.BASE_NETWORK_PATH))
                self.assertEqual(paths.network.read_bytes(), before)
                self.assertFalse((self.root / "unused.xml").exists())
                schedule = ET.parse(paths.transit_schedule).getroot()
                self.assertEqual(schedule.findall(".//stopFacility"), [])
                self.assertEqual(schedule.findall(".//transitLine"), [])
                vehicles = ET.parse(paths.transit_vehicles).getroot()
                self.assertEqual(vehicles.findall("{*}vehicle"), [])
                self.assertEqual([v.get("id") for v in vehicles.findall("{*}vehicleType")], ["unused_no_pt"])
                fleet = ET.parse(paths.uam_fleet).getroot()
                self.assertEqual(len(fleet.findall(".//vehicle")), 4)
                self.assertTrue(paths.manifest.is_file())

    def test_no_pt_demand_has_only_uam_and_car_alternatives(self):
        for raw in (dict(enabled=True, trains=[], buses=[]), dict(enabled=False)):
            with self.subTest(raw=raw), patch.object(config, "TRANSPORT_SUPPLY", raw):
                DemandGenerator().generate_demand(str(self.root / "population"))
                people = ET.parse(self.root / "population/population.xml").getroot().findall("person")
                self.assertEqual(len(people), 2)
                for person in people:
                    self.assertEqual(len(person.findall("plan")), 2)
                    self.assertEqual(person.findall('.//leg[@mode="pt"]'), [])
                    self.assertTrue(person.findall('.//leg[@mode="uam"]'))

    def test_explicit_pt_without_services_is_rejected_before_generation(self):
        for override in (dict(pt_plan_enabled=True), dict(initial_ground_plan="pt")):
            with self.subTest(override=override), patch.object(config, "DEMAND_EVENTS", [{**self.event, **override}]):
                with self.assertRaisesRegex(ValueError, "requests PT without any scheduled services"):
                    DemandGenerator().generate_demand(str(self.root / "population"))
                with self.assertRaisesRegex(ValueError, "requests PT without any scheduled services"):
                    pipeline.validate_configuration()

    def test_preflight_rejects_malformed_transport(self):
        with patch.object(config, "TRANSPORT_SUPPLY", dict(enabled=True, buses="invalid")):
            with self.assertRaisesRegex(ValueError, "Invalid TRANSPORT_SUPPLY"):
                pipeline.validate_configuration()

    def test_preflight_accepts_no_pt_without_writing_outputs(self):
        before = set(self.root.rglob("*"))
        with patch.object(pipeline.shutil, "which", return_value="java"):
            pipeline.validate_configuration()
        self.assertEqual(set(self.root.rglob("*")), before)

    def test_configured_bus_keeps_pt_alternatives(self):
        raw = dict(enabled=True, trains=[], buses=[dict(
            start_location=dict(name="A", x=0, y=0),
            destination_location=dict(name="B", x=1000, y=0),
            number_of_vehicles=2, frequency_minutes=30)])
        with patch.object(config, "TRANSPORT_SUPPLY", raw):
            self.assertEqual(len(normalise_transport_config(raw)["services"]), 2)
            DemandGenerator().generate_demand(str(self.root / "population"))
            self.assertEqual(len(ET.parse(self.root / "population/population.xml").getroot().findall('.//leg[@mode="pt"]')), 2)


if __name__ == "__main__":
    unittest.main()
