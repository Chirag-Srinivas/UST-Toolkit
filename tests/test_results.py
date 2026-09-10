from __future__ import annotations

import gzip
import tempfile
import unittest
from pathlib import Path

from module5 import ExtractionPaths, public_iteration_catalog, read_general_results


class ResultsTest(unittest.TestCase):
    def test_discovers_iterations_and_reads_duplicate_stopwatch_header(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outputs = root / "outputs"
            for number in (0, 2):
                directory = outputs / "ITERS" / f"it.{number}"
                directory.mkdir(parents=True)
                (directory / f"{number}.events.xml").write_text(
                    "<events/>", encoding="utf-8"
                )
                with gzip.open(
                    directory / f"{number}.trips.csv.gz",
                    "wt",
                    encoding="utf-8",
                    newline="",
                ) as stream:
                    stream.write(
                        "person;trav_time;wait_time;main_mode\n"
                        "p1;00:10:00;00:00:00;car\n"
                        f"p2;00:{20 + number:02d}:00;00:0{number}:00;pt\n"
                        "p3;00:20:00;00:00:00;car\n"
                    )

            (outputs / "scorestats.csv").write_text(
                "iteration;avg_executed;avg_worst;avg_average;avg_best\n"
                "0;1;1;1;1\n2;3;1;2;3\n",
                encoding="utf-8",
            )
            (outputs / "stopwatch.csv").write_text(
                "iteration;mobsim;replanning;iteration\n"
                "0;00:00:04;00:00:02;00:00:08\n"
                "2;00:00:05;00:00:03;00:00:10\n",
                encoding="utf-8",
            )
            paths = ExtractionPaths(
                events=outputs / "output_events.xml.gz",
                network=outputs / "output_network.xml.gz",
                design_report=root / "design.json",
                population=None,
                output_dir=outputs / "module5_analytics",
            )

            catalog = public_iteration_catalog(paths)
            results = read_general_results(paths)

            self.assertEqual(catalog["defaultIteration"], 2)
            self.assertEqual(
                [item["number"] for item in catalog["iterations"]], [0, 2]
            )
            self.assertEqual(results["runtime"][-1]["iteration"], 2)
            self.assertEqual(results["runtime"][-1]["totalSeconds"], 10)
            self.assertEqual(results["tripTimeModes"], ["car", "pt"])
            self.assertEqual(
                results["tripTimeStats"][0]["averageTravelMinutes"]["car"],
                15,
            )
            self.assertEqual(
                results["tripTimeStats"][-1]["averageWaitMinutes"]["pt"],
                2,
            )


if __name__ == "__main__":
    unittest.main()
