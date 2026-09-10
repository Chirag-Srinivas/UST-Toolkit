from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from background_traffic_generator import main


NETWORK_XML = """<?xml version="1.0" encoding="utf-8"?>
<network>
  <nodes>
    <node id="n1" x="0" y="0" />
    <node id="n2" x="10" y="0" />
    <node id="n3" x="10" y="10" />
    <node id="n4" x="0" y="10" />
    <node id="n5" x="100" y="100" />
    <node id="n6" x="110" y="100" />
  </nodes>
  <links>
    <link id="l1" from="n1" to="n2" modes="car" />
    <link id="l2" from="n2" to="n3" modes="car" />
    <link id="l3" from="n3" to="n4" modes="car" />
    <link id="l4" from="n4" to="n1" modes="car" />
    <link id="dead_end" from="n5" to="n6" modes="car" />
    <link id="walk" from="n1" to="n3" modes="walk" />
  </links>
</network>
"""


class BackgroundTrafficTest(unittest.TestCase):
    def test_cli_writes_population_beside_network(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            network = directory / "base_network.xml"
            network.write_text(NETWORK_XML, encoding="utf-8")

            with patch(
                "background_traffic_generator.BASE_DATA_DIRECTORY", directory
            ):
                exit_code = main(
                    [
                        "--network",
                        str(network),
                        "--output",
                        "smoke_background.xml",
                        "--agents",
                        "2",
                        "--candidate-links",
                        "10",
                        "--minimum-distance-km",
                        "0.001",
                        "--median-distance-km",
                        "0.005",
                        "--maximum-distance-km",
                        "0.020",
                        "--peak-spread-minutes",
                        "0",
                    ]
                )

            output = directory / "smoke_background.xml"
            self.assertEqual(exit_code, 0)
            self.assertTrue(output.is_file())
            root = ET.parse(output).getroot()
            self.assertEqual(root.attrib, {})
            people = root.findall("person")
            self.assertEqual(len(people), 2)
            self.assertEqual(len(root.findall("person/plan/leg")), 4)
            self.assertTrue(
                all(
                    leg.attrib == {"mode": "car", "routingMode": "car"}
                    for leg in root.findall("person/plan/leg")
                )
            )
            self.assertNotIn(
                "dead_end",
                {
                    activity.attrib["link"]
                    for activity in root.findall("person/plan/activity")
                },
            )


if __name__ == "__main__":
    unittest.main()
