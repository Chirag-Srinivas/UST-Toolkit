# module4_config.py - MATSim scoring, co-evolution, and run configuration

import os

import config
from module3_transport import normalise_transport_config
from xml_writer import writematsimconfig

class ConfigManager:
    def __init__(self):
        self.iterations = config.NITER
        self.memory = config.MPLANS
        self.innovation_disable_fraction = config.INNOVATION_DISABLE_FRACTION
        self.strategies_by_subpop = config.STRATEGIES_BY_SUBPOPULATION
        self.betawaithigh = config.BETAWAITHIGH
        self.betawaitlow = config.BETAWAITLOW
        self.betatravel = config.BETATRAVEL

    def generateconfig(self, outputfile):
        """Generate the master MATSim config."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.normpath(os.path.join(script_dir, ".."))
        transport_settings = normalise_transport_config(config.TRANSPORT_SUPPLY)
        transport_dir = os.path.join(
            project_root,
            "scenarios",
            transport_settings.get("output_directory", "transport"),
        )
        fleet_target = os.path.join(
            transport_dir, transport_settings.get("uam_fleet_file", "uam_fleet.xml")
        )
        schedule_target = os.path.join(
            transport_dir,
            transport_settings.get("transit_schedule_file", "transit_schedule.xml"),
        )
        transit_vehicles_target = os.path.join(
            transport_dir,
            transport_settings.get("transit_vehicles_file", "transit_vehicles.xml"),
        )
        network_target = os.path.join(
            project_root,
            "scenarios",
            "networks",
            (
                transport_settings.get("network_output_file", "network_transport.xml")
                if transport_settings.get("network", {}).get("strategy")
                == "pseudo_network"
                else "network_with_uam.xml"
            ),
        )
        required_supply = {
            "transport network": network_target,
            "transit schedule": schedule_target,
            "transit vehicles": transit_vehicles_target,
            "UAM fleet": fleet_target,
        }
        missing_supply = [
            f"{label}: {path}"
            for label, path in required_supply.items()
            if not os.path.isfile(path)
        ]
        if missing_supply:
            raise FileNotFoundError(
                "Module 3 transport supply is incomplete. Run `python -m "
                "module3_transport` first:\n" + "\n".join(missing_supply)
            )

        for subpop, strategy_set in self.strategies_by_subpop.items():
            total_prob = sum(strategy_set.values())
            if abs(total_prob - 1.0) > 1e-9:
                raise ValueError(
                    f"Strategy weights for '{subpop}' sum to {total_prob}, not 1.0."
                )

        configparams = {
            "networkfile": network_target.replace("\\", "/"),
            "populationfile": os.path.join(
                project_root,
                "scenarios",
                "populations",
                "population.xml",
            ).replace("\\", "/"),
            "outputdir": os.path.join(project_root, "outputs").replace("\\", "/"),
            "iterations": self.iterations,
            "write_plans_interval": config.WRITE_PLANS_INTERVAL,
            "write_experienced_plans": config.WRITE_EXPERIENCED_PLANS,
            "random_seed": config.DEMAND_RANDOM_SEED,
            "memory": self.memory,
            "innovation_disable_fraction": self.innovation_disable_fraction,
            "strategies_by_subpop": self.strategies_by_subpop,
            "betawaithigh": self.betawaithigh,
            "betawaitlow": self.betawaitlow,
            "betatravel": self.betatravel,
            "utility_of_line_switch": config.UTILITY_OF_LINE_SWITCH,
            "vehiclesfile": fleet_target.replace("\\", "/"),
            "transit_schedule_file": schedule_target.replace("\\", "/"),
            "transit_vehicles_file": transit_vehicles_target.replace("\\", "/"),
            "transit_routing": transport_settings.get("routing", {}),
            "uam_access_egress_modes": config.UAM_ACCESS_EGRESS_MODES,
            "uam_search_radius": config.UAM_SEARCH_RADIUS,
            "uam_max_pooling_wait_time": config.UAM_MAX_POOLING_WAIT_TIME,
            "vspExperimental": {
                "vspDefaultsCheckingLevel": "warn",
                "isGeneratingBoardingDeniedEvent": "false",
                "isAbleToOverwritePtInteractionParams": "false",
            },
        }

        writematsimconfig(configparams, outputfile)

if __name__ == "__main__":
    print("--- Module 4 ConfigManager initiated ---")
    manager = ConfigManager()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, ".."))
    config_target = os.path.join(project_root, "scenarios", "configs", "config.xml")

    os.makedirs(os.path.dirname(config_target), exist_ok=True)
    manager.generateconfig(outputfile=config_target)

    print("--- Module 4 complete ---")
