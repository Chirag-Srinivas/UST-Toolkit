# pipeline.py - Optimised execution flow for the UAM Scenario Toolkit (UST)

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import threading
import urllib.request
from urllib.parse import urlparse
import webbrowser
from pathlib import Path
try:
    import psutil
except (ImportError, OSError):
    psutil = None
import config

# Import all UST modules
from module0_network_cleaning import NetworkPreparer
from module1_topology import TopologyBuilder
from module2_demand import DemandGenerator
from module3_transport import TransportSupplyGenerator, normalise_transport_config
from module4_config import ConfigManager
from module5 import AnalyticsExtractor, ExtractionPaths, SCHEMA_VERSION


def validate_configuration():
    """Fail early with an actionable list of missing scenario inputs."""
    errors = []
    scheduled_transport = False
    try:
        scheduled_transport = bool(normalise_transport_config(config.TRANSPORT_SUPPLY)["services"])
    except (ValueError, TypeError, KeyError) as exc:
        errors.append(f"Invalid TRANSPORT_SUPPLY: {exc}")
    base_network = Path(config.BASE_NETWORK_PATH).expanduser()
    matsim_jar = Path(config.MATSIM_JAR_PATH).expanduser()

    scenario_name = str(getattr(config, "SCENARIO_NAME", "")).strip()
    if not scenario_name or scenario_name == "my_uam_scenario":
        errors.append("Replace the default SCENARIO_NAME in src/config.py.")
    if not base_network.is_file():
        errors.append(
            "Add a MATSim network at data/base_network.xml or set "
            "BASE_NETWORK_PATH/UST_BASE_NETWORK_PATH."
        )
    if not matsim_jar.is_file():
        errors.append(
            "The MATSim-UAM JAR is missing. Expected "
            f"{matsim_jar}."
        )
    if shutil.which("java") is None:
        errors.append("Install Java 21 and make the `java` command available on PATH.")

    vertiports = getattr(config, "VERTIPORTS", [])
    if not isinstance(vertiports, list) or len(vertiports) < 2:
        errors.append("Define at least two VERTIPORTS in src/config.py.")
        vertiport_ids = set()
        stand_capacity = 0
    else:
        vertiport_ids = {
            str(item.get("id"))
            for item in vertiports
            if isinstance(item, dict) and item.get("id") is not None
        }
        if len(vertiport_ids) != len(vertiports):
            errors.append("Every vertiport needs a unique `id`.")
        stand_capacity = 0
        for index, vertiport in enumerate(vertiports):
            try:
                count = int(vertiport["layout"]["stands"]["count"])
            except (KeyError, TypeError, ValueError):
                errors.append(
                    f"VERTIPORTS[{index}] needs layout.stands.count as a whole number."
                )
                continue
            if count <= 0:
                errors.append(f"VERTIPORTS[{index}] must have at least one stand.")
            stand_capacity += max(0, count)

    routes = getattr(config, "AERIAL_ROUTES", [])
    if not isinstance(routes, list) or not routes:
        errors.append("Define at least one AERIAL_ROUTES entry in src/config.py.")
    else:
        for index, route in enumerate(routes):
            if not isinstance(route, dict):
                errors.append(f"AERIAL_ROUTES[{index}] must be a dictionary.")
                continue
            endpoints = {
                str(route.get("from_vertiport")),
                str(route.get("to_vertiport")),
            }
            if not endpoints.issubset(vertiport_ids):
                errors.append(
                    f"AERIAL_ROUTES[{index}] references an unknown vertiport."
                )

    demand_events = getattr(config, "DEMAND_EVENTS", [])
    if not isinstance(demand_events, list) or not demand_events:
        errors.append("Define at least one DEMAND_EVENTS entry in src/config.py.")
    else:
        for index, event in enumerate(demand_events):
            if not isinstance(event, dict):
                errors.append(f"DEMAND_EVENTS[{index}] must be a dictionary.")
                continue
            if not scheduled_transport and (
                event.get("pt_plan_enabled", False)
                or str(event.get("initial_ground_plan", "car")).lower() == "pt"
            ):
                errors.append(
                    f"DEMAND_EVENTS[{index}] requests PT without any scheduled services."
                )
            event_vertiports = {
                str(event.get("vertiport_id")),
                str(event.get("dest_vertiport_id")),
            }
            if not event_vertiports.issubset(vertiport_ids):
                errors.append(
                    f"DEMAND_EVENTS[{index}] references an unknown vertiport."
                )

    try:
        fleet_size = int(getattr(config, "FLEET_SIZE", 0))
    except (TypeError, ValueError):
        fleet_size = 0
    if fleet_size <= 0:
        errors.append("Set FLEET_SIZE to a positive whole number.")
    elif stand_capacity and fleet_size > stand_capacity:
        errors.append(
            f"FLEET_SIZE ({fleet_size}) exceeds total stand capacity ({stand_capacity})."
        )

    base_population = str(getattr(config, "BASE_POPULATION_PATH", "")).strip()
    if base_population and not Path(base_population).expanduser().is_file():
        errors.append(f"BASE_POPULATION_PATH does not exist: {base_population}")

    if getattr(config, "MODULE5_AUTO_EXTRACT", True):
        module5_crs = str(getattr(config, "MODULE5_CRS", "")).strip()
        if not module5_crs:
            errors.append(
                "Set MODULE5_CRS (or UST_NETWORK_CRS) to the base network's EPSG code."
            )
        else:
            try:
                from pyproj import CRS

                CRS.from_user_input(module5_crs)
            except Exception:
                errors.append(f"MODULE5_CRS is not a recognised CRS: {module5_crs}")

    if errors:
        details = "\n".join(f"  - {message}" for message in errors)
        raise ValueError(
            "Scenario setup is incomplete:\n"
            f"{details}\n"
            "Follow experiment_inputs/README.md, then run the pipeline again."
        )

def prepare_output_directory(output_dir, project_root):
    """
    Replace the project's MATSim output directory with a new empty directory.

    The strict path checks ensure cleanup cannot escape the expected
    <project_root>/outputs location if a path is changed accidentally.
    """
    output_path = Path(output_dir).resolve()
    project_path = Path(project_root).resolve()
    expected_output_path = (project_path / "outputs").resolve()

    if output_path != expected_output_path:
        raise ValueError(
            "Refusing to clean an unexpected output path:\n"
            f"Requested: {output_path}\n"
            f"Expected:  {expected_output_path}"
        )

    if output_path.parent != project_path or output_path.name.lower() != "outputs":
        raise ValueError(f"Unsafe MATSim output path: {output_path}")

    if output_path.exists():
        print(f"[Pipeline] Removing previous MATSim outputs:\n{output_path}")
        shutil.rmtree(output_path)

    output_path.mkdir(parents=False, exist_ok=False)
    print(f"[Pipeline] Created empty MATSim output directory:\n{output_path}")


def _module5_health(url, timeout_s=1.0):
    try:
        with urllib.request.urlopen(f"{url}/api/health", timeout=timeout_s) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else None
    except (OSError, ValueError, urllib.error.URLError):
        return None


def _module5_is_healthy(url, timeout_s=1.0):
    payload = _module5_health(url, timeout_s)
    return bool(
        payload
        and payload.get("status") == "ok"
        and payload.get("module") == 5
        and payload.get("schemaVersion") == SCHEMA_VERSION
    )


def _stop_incompatible_local_module5(url, health_payload, timeout_s=5.0):
    """Stop an older local Module 5 process that owns the requested port."""
    if psutil is None:
        return False
    parsed = urlparse(url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return False
    if health_payload.get("status") != "ok" or health_payload.get("module") != 5:
        return False

    port = parsed.port
    listeners = {
        connection.pid
        for connection in psutil.net_connections(kind="inet")
        if connection.pid
        and connection.status == psutil.CONN_LISTEN
        and connection.laddr.port == port
    }
    if len(listeners) != 1:
        return False

    process = psutil.Process(listeners.pop())
    process.terminate()
    try:
        process.wait(timeout=timeout_s)
    except psutil.TimeoutExpired:
        return False
    return True


def launch_module5_server(script_dir, host, port, startup_timeout_s=60.0):
    """Start Module 5 independently and return only after it is reachable."""
    url = f"http://{host}:{port}"
    running_health = _module5_health(url)
    if (
        running_health
        and running_health.get("status") == "ok"
        and running_health.get("module") == 5
        and running_health.get("schemaVersion") == SCHEMA_VERSION
    ):
        print(f"[Module 5] Reusing the running analytics server at {url}")
        webbrowser.open(url)
        return url
    if running_health:
        running_schema = running_health.get("schemaVersion", "unknown")
        if not _stop_incompatible_local_module5(url, running_health):
            raise RuntimeError(
                f"Port {port} is occupied by an incompatible service. "
                f"Expected Module 5 schema {SCHEMA_VERSION}; received "
                f"{running_schema}. Stop that service and run the pipeline again."
            )
        print(
            f"[Module 5] Replacing stale analytics server "
            f"(schema {running_schema}) with schema {SCHEMA_VERSION}"
        )

    log_dir = Path(script_dir) / "tmp"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "module5_server_stdout.log"
    stderr_path = log_dir / "module5_server_stderr.log"
    command = [
        sys.executable,
        str(Path(script_dir) / "local_server.py"),
        "--host",
        host,
        "--port",
        str(port),
        "--no-browser",
    ]
    popen_options = {
        "cwd": script_dir,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        popen_options["creationflags"] = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        )
    else:
        popen_options["start_new_session"] = True

    with stdout_path.open("w", encoding="utf-8") as stdout_log, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_log:
        process = subprocess.Popen(
            command,
            stdout=stdout_log,
            stderr=stderr_log,
            **popen_options,
        )

    deadline = time.monotonic() + startup_timeout_s
    while time.monotonic() < deadline:
        if _module5_is_healthy(url):
            print(f"[Module 5] Analytics server ready at {url}")
            webbrowser.open(url)
            return url
        if process.poll() is not None:
            break
        time.sleep(0.5)

    error_tail = ""
    if stderr_path.exists():
        error_tail = stderr_path.read_text(encoding="utf-8", errors="replace")[-2000:]
    raise RuntimeError(
        f"Module 5 did not become reachable at {url}. "
        f"See {stderr_path}.\n{error_tail}"
    )

def run_matsim_cleaner(matsim_jar, input_xml, output_xml, phase_name):
    """
    Executes MATSim's native Java NetworkCleaner via terminal, 
    wrapped with a Python-native MemoryObserver to monitor JVM heap usage.
    """
    print(f"\n[Java Execution: {phase_name}] Running MATSim NetworkCleaner on {input_xml}...")
    
    # Construct the Java command with strict memory bounds
    command = [
        "java", 
        "-Xmx8G",           # Allocates 8GB of RAM to prevent GC thrashing
        "-cp", matsim_jar, 
        "org.matsim.run.NetworkCleaner", 
        input_xml, output_xml
    ]
    
    # Start the Java process asynchronously
    process = subprocess.Popen(command)
    
    # Define our custom Memory Observer
    def memory_observer():
        try:
            java_proc = psutil.Process(process.pid)
            print(f"[MemoryObserver] Attached to Java JVM (PID: {process.pid})")
            while process.poll() is None:
                mem_mb = java_proc.memory_info().rss / (1024 * 1024)
                print(f"[MemoryObserver] {phase_name} JVM currently using: {mem_mb:.2f} MB RAM")
                time.sleep(30) 
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if psutil is not None:
        observer_thread = threading.Thread(target=memory_observer, daemon=True)
        observer_thread.start()
    else:
        print("[MemoryObserver] psutil unavailable; continuing without RSS monitoring.")
    
    process.wait()
    
    if process.returncode == 0:
        print(f"[Java Execution] {phase_name} Network successfully cleaned and saved to {output_xml}")
    else:
        print(f"\nERROR: MATSim NetworkCleaner failed during {phase_name}.")
        raise subprocess.CalledProcessError(process.returncode, command)

def main(check_only=False):
    print("==================================================")
    print("  Initiating UAM Scenario Toolkit (UST) Pipeline  ")
    print("==================================================\n")
    
    start_time = time.time()

    validate_configuration()
    if check_only:
        print("Scenario configuration check passed.")
        return
    
    # Define absolute paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, '..'))
    network_dir = os.path.join(project_root, 'scenarios', 'networks')
    population_dir = os.path.join(project_root, 'scenarios', 'populations')
    config_target = os.path.join(project_root, 'scenarios', 'configs', 'config.xml')
    transport_generator = TransportSupplyGenerator()
    transport_settings = transport_generator.settings
    transport_dir = os.path.join(
        project_root,
        'scenarios',
        transport_settings.get('output_directory', 'transport'),
    )
    transport_network = os.path.join(
        network_dir,
        transport_settings.get('network_output_file', 'network_transport.xml'),
    )
    output_dir = os.path.join(project_root, 'outputs')
    
    matsim_jar = os.path.abspath(os.path.expanduser(config.MATSIM_JAR_PATH))
    
    # Optimised File Path Tracking
    base_net_raw = getattr(config, 'BASE_NETWORK_PATH', os.path.join(script_dir, '..', 'data', 'base_network.xml'))
    base_net_prepped = os.path.join(network_dir, 'base_network_prepped.xml')
    base_net_pre_cleaned = os.path.join(network_dir, 'base_network_cleaned.xml')
    final_network = os.path.join(network_dir, 'network_with_uam.xml')

    # ==========================================================
    # STEP 0 : Base Network Preparation (Optional)
    # ==========================================================

    if getattr(config, "REBUILD_NETWORK", True):

        print("\n[Pipeline] REBUILD_NETWORK=True")
        print("[Pipeline] Running Module 0 and MATSim NetworkCleaner...")

        preparer = NetworkPreparer()
        preparer.enforce_matsim_header(
            base_net_raw,
            base_net_prepped
        )

        run_matsim_cleaner(
            matsim_jar,
            base_net_prepped,
            base_net_pre_cleaned,
            "Pre-Clean"
        )

    else:

        print("\n[DEBUG MODE]")
        print("[Pipeline] Skipping Module 0 and NetworkCleaner.")
        print(f"[Pipeline] Using existing cleaned base network:\n{base_net_pre_cleaned}")

    if not os.path.exists(base_net_pre_cleaned):
        raise FileNotFoundError(
            f"Cannot find cleaned base network:\n{base_net_pre_cleaned}"
        )

    # ==========================================================
    # STEP 1 : ALWAYS rebuild the micro topology
    # ==========================================================

    print("\nSTEP 1: Executing Module 1 (TopologyBuilder)...")

    builder = TopologyBuilder()

    builder.build_network(
        output_dir=network_dir,
        base_network_path=base_net_pre_cleaned
    )

    os.replace(
        os.path.join(network_dir, "network_micro.xml"),
        final_network
    )

    print(f"[Pipeline] Updated network written to:\n{final_network}")

    print("\nSTEP 2: Executing Module 2 (DemandGenerator)...")
    dg = DemandGenerator()
    dg.generate_demand(output_dir=population_dir)

    print("\nSTEP 3: Executing Module 3 (TransportSupplyGenerator)...")
    transport_generator.generate(
        base_network=Path(final_network),
        network_output=Path(transport_network),
        output_directory=Path(transport_dir),
    )

    print("\nSTEP 4: Executing Module 4 (ConfigManager)...")
    manager = ConfigManager()
    manager.generateconfig(outputfile=config_target)

    print("\n==================================================")
    print("  STEP 5: Executing MATSim Java Engine...         ")
    print("==================================================")
    
    if not os.path.exists(matsim_jar):
        print(f"\nWARNING: Could not find matsim.jar at {matsim_jar}")
        print(
            "Set MATSIM_JAR_PATH in config.py or the UST_MATSIM_JAR_PATH "
            "environment variable to your MATSim-UAM JAR."
        )
        return

    if getattr(config, 'AUTO_CLEAN_OUTPUTS', True):
        prepare_output_directory(output_dir, project_root)
    else:
        os.makedirs(output_dir, exist_ok=True)
        print("[Pipeline] AUTO_CLEAN_OUTPUTS=False; preserving existing MATSim outputs.")

    try:
        command = [
            "java",
            "-Xmx8G",           
            "-jar", matsim_jar, 
            config_target       
        ]
        run_options = {}
        if os.name == "nt":
            run_options["creationflags"] = (
                getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )
        completed = subprocess.run(command, check=False, **run_options)
        if completed.returncode != 0:
            print(
                f"\nERROR: MATSim Java process exited with code "
                f"{completed.returncode}."
            )
            raise subprocess.CalledProcessError(completed.returncode, command)
        
    except subprocess.CalledProcessError:
        print("\nERROR: MATSim simulation failed or crashed.")
        # Propagate the Java failure so callers receive the actual non-zero
        # exit instead of discovering it later as missing output files.
        raise

    # ==========================================================
    # STEP 6: Build the connected Module 5 analytics bundle
    # ==========================================================
    analytics_dir = os.path.join(output_dir, "module5_analytics")
    if getattr(config, "MODULE5_AUTO_EXTRACT", True):
        print("\nSTEP 6: Extracting Module 5 analytics...")
        try:
            analytics_paths = ExtractionPaths(
                events=Path(output_dir) / "output_events.xml.gz",
                network=Path(output_dir) / "output_network.xml.gz",
                design_report=Path(network_dir) / "vertiport_design_report.json",
                population=Path(population_dir) / "population.xml",
                output_dir=Path(analytics_dir),
                background_traffic_enabled=bool(
                    str(getattr(config, "BASE_POPULATION_PATH", "")).strip()
                ),
            )
            bundle = AnalyticsExtractor(
                analytics_paths,
                crs=getattr(config, "MODULE5_CRS", ""),
            ).extract(force=True)
            print(f"[Module 5] Analytics bundle ready:\n{bundle}")
        except Exception as exc:
            print(f"\nWARNING: Module 5 extraction failed: {exc}")
            print(
                "The MATSim run is complete. Re-run analytics with "
                "`python -m module5 extract --force` after resolving the issue."
            )

    if getattr(config, "MODULE5_AUTO_LAUNCH", False):
        host = getattr(config, "MODULE5_HOST", "127.0.0.1")
        port = int(getattr(config, "MODULE5_PORT", 8765))
        try:
            launch_module5_server(script_dir, host, port)
        except Exception as exc:
            print(f"\nWARNING: Module 5 server failed to start: {exc}")
        
    elapsed = round((time.time() - start_time) / 60, 2)
    
    print("\n==================================================")
    print(f"  MATSim Simulation Complete in {elapsed} minutes.")
    print("  Outputs generated in the /outputs directory.")
    print("  Module 5 analytics have been extracted.")
    print(
        f"  Launch with: {sys.executable} -m module5 serve "
        f"--host {getattr(config, 'MODULE5_HOST', '127.0.0.1')} "
        f"--port {getattr(config, 'MODULE5_PORT', 8765)}"
    )
    print("==================================================")

def build_parser():
    parser = argparse.ArgumentParser(
        description="Build and run a configured UAM MATSim scenario."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate required files and top-level scenario parameters, then exit.",
    )
    return parser


if __name__ == "__main__":
    main(check_only=build_parser().parse_args().check)
