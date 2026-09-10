# module2_demand.py - Socio-Economic Population Synthesis
import config
import random
import os
from uam_geometry import vertiport_geometry
from xml_writer import write_matsim_population, merge_matsim_population
from module3_transport import normalise_transport_config

class DemandGenerator:
    def __init__(self):
        self.demand_events = getattr(config, 'DEMAND_EVENTS', [])
        self.base_population = getattr(config, 'BASE_POPULATION_PATH', "")
        self.random_seed = getattr(config, "DEMAND_RANDOM_SEED", 4711)
        self.vehicle_type = getattr(config, 'UAM_VEHICLE_TYPE', {})
        self.design_rules = getattr(config, 'VERTIPORT_DESIGN_RULES', {})
        self.scheduled_transport = bool(
            normalise_transport_config(config.TRANSPORT_SUPPLY)["services"]
        )
        self.vertiports_by_id = {
            str(vp["id"]): vp
            for vp in getattr(config, 'VERTIPORTS', [])
            if isinstance(vp, dict) and "id" in vp
        }

    def generate_demand(self, output_dir="../scenarios/populations"):
        print("--- Module 2: DemandGenerator Initiated ---")
        if not self.demand_events:
            print("No demand events found in config.py.")
            return

        rng = random.Random(self.random_seed)
        all_agents = []
        global_agent_counter = 1

        # Track the array index using enumerate to align origin/dest links dynamically
        for idx, event in enumerate(self.demand_events):
            event_name = event.get("source_name", f"Event_{idx}")
            vp_id = str(event["vertiport_id"])
            if vp_id not in self.vertiports_by_id:
                raise ValueError(
                    f"Demand event '{event_name}' references unknown vertiport_id '{vp_id}'."
                )
            dest_vp_id = str(event.get("dest_vertiport_id", "2"))
            if dest_vp_id not in self.vertiports_by_id:
                raise ValueError(
                    f"Demand event '{event_name}' references unknown destination "
                    f"vertiport_id '{dest_vp_id}'."
                )

            origin_vertiport = self.vertiports_by_id[vp_id]
            destination_vertiport = self.vertiports_by_id[dest_vp_id]
            geometry = vertiport_geometry(
                origin_vertiport, self.vehicle_type, self.design_rules
            )
            destination_geometry = vertiport_geometry(
                destination_vertiport, self.vehicle_type, self.design_rules
            )
            entry_x, entry_y = geometry["terminal"]
            boarding_x = (
                geometry["station_stand"]["center"][0] + geometry["apron"][0]
            ) / 2.0
            boarding_y = (
                geometry["station_stand"]["center"][1] + geometry["apron"][1]
            ) / 2.0
            arrival_x = (
                destination_geometry["station_stand"]["center"][0]
                + destination_geometry["apron"][0]
            ) / 2.0
            arrival_y = (
                destination_geometry["station_stand"]["center"][1]
                + destination_geometry["apron"][1]
            ) / 2.0
            
            # Generate the complete UAM-eligible cohort independently of the
            # initially selected plan. Every generated agent receives UAM,
            # car, and (when enabled) PT alternatives in population.xml.
            d_pulse = int(event["c_source"] * event["uam_adoption"])
            initial_uam_count = int(event.get("initial_uam_count", d_pulse))
            if not 0 <= initial_uam_count <= d_pulse:
                raise ValueError(
                    f"Demand event '{event_name}' initial_uam_count "
                    f"{initial_uam_count} must be between 0 and {d_pulse}."
                )
            initial_ground_plan = str(
                event.get("initial_ground_plan", "car")
            ).lower()
            if initial_ground_plan not in {"car", "pt"}:
                raise ValueError(
                    f"Demand event '{event_name}' initial_ground_plan must be "
                    "'car' or 'pt'."
                )
            pt_plan_enabled = bool(event.get("pt_plan_enabled", self.scheduled_transport))
            if not self.scheduled_transport and (pt_plan_enabled or initial_ground_plan == "pt"):
                raise ValueError(
                    f"Demand event '{event_name}' requests PT without any scheduled services."
                )
            initial_plan_rng = random.Random(self.random_seed + idx * 1_000_003)
            initial_uam_indices = set(
                initial_plan_rng.sample(range(d_pulse), initial_uam_count)
            )
            delay_mean = event["release_delay_mean_s"]
            delay_std = event["release_delay_std_s"]
            if delay_std < 0:
                raise ValueError(
                    f"Demand event '{event_name}' has a negative release-delay "
                    "standard deviation."
                )

            for local_index in range(d_pulse):
                agent_id = f"Pax_{global_agent_counter}_{vp_id}"
                global_agent_counter += 1

                transfer_delay = max(0, rng.gauss(delay_mean, delay_std))
                dep_time = event["t_event"] + transfer_delay

                # Format time to strict MATSim HH:MM:SS standard
                h = int(dep_time // 3600)
                m = int((dep_time % 3600) // 60)
                s = int(dep_time % 60)
                formatted_time = f"{h:02d}:{m:02d}:{s:02d}"

                # Assign socio-economic tags for co-evolution scoring in Module 4.
                subpop = (
                    "high_urgency"
                    if rng.random() < event["high_urgency_ratio"]
                    else "low_urgency"
                )

                # Construct the comprehensive agent payload
                all_agents.append({
                    "id": agent_id,
                    # Separate links keep the car, terminal walk, and UAM
                    # portions as three distinct MATSim trips.
                    "origin_link_exact": f"link_origin_egress_{idx}",
                    "vertiport_entry_link_exact": f"link_base_to_vt_interface_{vp_id}",
                    "vertiport_boarding_link_exact": f"link_stand_apron_{vp_id}",
                    "vertiport_arrival_link_exact": f"link_stand_apron_{dest_vp_id}",
                    "dest_link_exact": f"link_dest_access_{idx}",
                    "vertiport_entry_x": entry_x,
                    "vertiport_entry_y": entry_y,
                    "vertiport_boarding_x": boarding_x,
                    "vertiport_boarding_y": boarding_y,
                    "vertiport_arrival_x": arrival_x,
                    "vertiport_arrival_y": arrival_y,
                    "origin_x": event["origin_x"], 
                    "origin_y": event["origin_y"],
                    "dest_x": event["dest_x"], 
                    "dest_y": event["dest_y"], 
                    "departure_time": formatted_time,
                    "subpopulation": subpop,
                    "vertiport_id": vp_id,
                    "dest_vertiport_id": dest_vp_id,
                    "access_mode": event.get("access_mode", "car"),
                    "flight_mode": event.get("flight_mode", "uam"),
                    "initial_plan": (
                        "uam"
                        if local_index in initial_uam_indices
                        else initial_ground_plan
                    ),
                    "pt_plan_enabled": pt_plan_enabled,
                })

        output_file = f"{output_dir}/population.xml"
        
        # Merge or write isolated population
        if self.base_population and os.path.exists(self.base_population):
            merge_matsim_population(self.base_population, all_agents, output_file)
        else:
            write_matsim_population(all_agents, output_path=output_file)
            
        print(f"Total Synthesised: {len(all_agents)} agents. Module 2 Complete.\n")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_dir = os.path.normpath(os.path.join(script_dir, "..", "scenarios", "populations"))
    generator = DemandGenerator()
    generator.generate_demand(output_dir=target_dir)
