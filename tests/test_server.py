import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from module5 import (
    AnalyticsExtractor,
    ExtractionPaths,
    _paths_from_args,
    _scenario_name_from_args,
    build_parser,
    create_app,
)


class Module5ServerTests(unittest.TestCase):
    def test_default_iteration_reuses_top_level_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outputs = root / "outputs"
            iteration_dir = outputs / "ITERS" / "it.10"
            analytics_dir = outputs / "module5_analytics"
            iteration_dir.mkdir(parents=True)
            analytics_dir.mkdir()

            events = outputs / "output_events.xml"
            network = outputs / "output_network.xml"
            design_report = root / "vertiport_design_report.json"
            population = root / "population.xml"
            iteration_events = iteration_dir / "10.events.xml"
            for path in (events, network, design_report, population, iteration_events):
                path.write_text("", encoding="utf-8")

            bundle = analytics_dir / "analytics_bundle.json"
            bundle.write_text('{"schemaVersion":8}', encoding="utf-8")
            paths = ExtractionPaths(
                events=events,
                network=network,
                design_report=design_report,
                population=population,
                output_dir=analytics_dir,
            )

            with patch.object(
                AnalyticsExtractor,
                "extract",
                return_value=bundle,
            ) as extract:
                app = create_app(paths, crs="EPSG:27700")
                analytics_route = next(
                    route
                    for route in app.routes
                    if getattr(route, "path", None) == "/api/analytics"
                )
                health_route = next(
                    route
                    for route in app.routes
                    if getattr(route, "path", None) == "/api/health"
                )
                response = analytics_route.endpoint(iteration=10)
                health = health_route.endpoint()

            self.assertEqual(Path(response.path), bundle)
            self.assertEqual(extract.call_count, 1)
            self.assertEqual(health["schemaVersion"], 8)

    def test_cache_only_serves_existing_bundle_without_extracting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            analytics_dir = root / "outputs" / "module5_analytics"
            analytics_dir.mkdir(parents=True)
            bundle = analytics_dir / "analytics_bundle.json"
            bundle.write_text('{"schemaVersion":8}', encoding="utf-8")
            (analytics_dir / "manifest.json").write_text(
                '{"schemaVersion":8}', encoding="utf-8"
            )
            paths = ExtractionPaths(
                events=root / "outputs" / "output_events.xml.gz",
                network=root / "outputs" / "output_network.xml.gz",
                design_report=root / "input_snapshots" / "vertiport_design_report.json",
                population=root / "input_snapshots" / "population.xml",
                output_dir=analytics_dir,
                background_traffic_enabled=True,
            )

            with patch.object(AnalyticsExtractor, "extract") as extract:
                app = create_app(
                    paths,
                    cache_only=True,
                    scenario_name="T1_test",
                )
                health_route = next(
                    route
                    for route in app.routes
                    if getattr(route, "path", None) == "/api/health"
                )
                iterations_route = next(
                    route
                    for route in app.routes
                    if getattr(route, "path", None) == "/api/iterations"
                )
                health = health_route.endpoint()
                iterations = iterations_route.endpoint()

            extract.assert_not_called()
            self.assertTrue(health["cacheOnly"])
            self.assertEqual(health["scenarioName"], "T1_test")
            self.assertEqual(json.loads(iterations.body)["iterations"], [])

    def test_archived_run_arguments_resolve_inputs_and_background(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "archived_example"
            (run_dir / "outputs").mkdir(parents=True)
            (run_dir / "input_snapshots").mkdir()
            (run_dir / "run_manifest.json").write_text(
                """{
                  "run_id": "archived_example",
                  "effective_parameters": {"background_agents": 5000}
                }""",
                encoding="utf-8",
            )
            args = build_parser().parse_args(
                ["serve", "--run-dir", str(run_dir), "--cache-only"]
            )
            paths = _paths_from_args(args)

            self.assertEqual(
                paths.events, (run_dir / "outputs" / "output_events.xml.gz").resolve()
            )
            self.assertEqual(
                paths.population,
                (run_dir / "input_snapshots" / "population.xml").resolve(),
            )
            self.assertEqual(
                paths.output_dir,
                (run_dir / "outputs" / "module5_analytics").resolve(),
            )
            self.assertTrue(paths.background_traffic_enabled)
            self.assertEqual(_scenario_name_from_args(args), "archived_example")

    def test_cache_only_can_lazily_expose_and_extract_missing_iterations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outputs = root / "outputs"
            iteration_dir = outputs / "ITERS" / "it.10"
            earlier_iteration_dir = outputs / "ITERS" / "it.9"
            analytics_dir = outputs / "module5_analytics"
            iteration_dir.mkdir(parents=True)
            earlier_iteration_dir.mkdir(parents=True)
            analytics_dir.mkdir()
            (iteration_dir / "10.events.xml").write_text("", encoding="utf-8")
            (earlier_iteration_dir / "9.events.xml").write_text("", encoding="utf-8")
            (analytics_dir / "analytics_bundle.json").write_text(
                '{"schemaVersion":8}', encoding="utf-8"
            )
            (analytics_dir / "manifest.json").write_text(
                '{"schemaVersion":8}', encoding="utf-8"
            )
            paths = ExtractionPaths(
                events=outputs / "output_events.xml.gz",
                network=outputs / "output_network.xml.gz",
                design_report=root / "input_snapshots" / "vertiport_design_report.json",
                population=root / "input_snapshots" / "population.xml",
                output_dir=analytics_dir,
            )
            iteration_bundle = (
                analytics_dir / "iterations" / "it.9" / "analytics_bundle.json"
            )

            with patch.object(
                AnalyticsExtractor, "extract", return_value=iteration_bundle
            ) as extract:
                app = create_app(
                    paths,
                    cache_only=True,
                    extract_missing_iterations=True,
                    crs="EPSG:27700",
                )
                iterations_route = next(
                    route
                    for route in app.routes
                    if getattr(route, "path", None) == "/api/iterations"
                )
                analytics_route = next(
                    route
                    for route in app.routes
                    if getattr(route, "path", None) == "/api/analytics"
                )
                catalog = json.loads(iterations_route.endpoint().body)
                response = analytics_route.endpoint(iteration=9)

            self.assertEqual(
                [item["number"] for item in catalog["iterations"]], [9, 10]
            )
            self.assertEqual(Path(response.path), iteration_bundle)
            extract.assert_called_once()


if __name__ == "__main__":
    unittest.main()
