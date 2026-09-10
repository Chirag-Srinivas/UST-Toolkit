# xml_writer.py - Centralised XML generator for the MATSim pipeline
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os


def _append_multimodal_uam_plan(plan, agent):
    """Append an explicit car -> walk -> UAM plan for one passenger."""
    orig_link = str(agent.get('origin_link_exact', agent.get('origin_link')))
    dest_link = str(agent.get('dest_link_exact', agent.get('dest_link')))
    entry_link = str(agent.get(
        'vertiport_entry_link_exact',
        agent.get(
            'vertiport_entry_link',
            agent.get('interface_link_exact', agent.get('interface_link', orig_link))
        )
    ))
    boarding_link = str(agent.get(
        'vertiport_boarding_link_exact',
        agent.get('vertiport_boarding_link', entry_link)
    ))
    arrival_link = str(agent.get(
        'vertiport_arrival_link_exact',
        agent.get('vertiport_arrival_link', boarding_link)
    ))

    # Trip 1: the passenger uses the configured access mode to the vertiport.
    ET.SubElement(
        plan,
        'activity',
        type="dummyorigin",
        link=orig_link,
        x=str(agent.get('origin_x', '0')),
        y=str(agent.get('origin_y', '0')),
        end_time=str(agent.get('departure_time', '0'))
    )
    access_mode = str(agent.get('access_mode', 'car'))
    ET.SubElement(plan, 'leg', mode=access_mode, routingMode=access_mode)

    # These are main activities, not UAM stage activities. They preserve the
    # trip boundaries when MATSim prepares or reroutes the selected plan.
    ET.SubElement(
        plan,
        'activity',
        type="vertiport_entry",
        link=entry_link,
        x=str(agent['vertiport_entry_x']),
        y=str(agent['vertiport_entry_y']),
        max_dur="00:00:01"
    )

    # Trip 2: the passenger moves through the terminal to the UAM station.
    ET.SubElement(plan, 'leg', mode="walk", routingMode="walk")
    ET.SubElement(
        plan,
        'activity',
        type="vertiport_boarding",
        link=boarding_link,
        x=str(agent['vertiport_boarding_x']),
        y=str(agent['vertiport_boarding_y']),
        max_dur="00:00:01"
    )

    # Trip 3: MATSim-UAM expands this leg and creates uam_interaction stages.
    # Terminating it at the destination station prevents the extension from
    # requesting a car route from an internal stand/apron link.
    flight_mode = str(agent.get('flight_mode', 'uam'))
    ET.SubElement(plan, 'leg', mode=flight_mode, routingMode=flight_mode)
    ET.SubElement(
        plan,
        'activity',
        type="vertiport_arrival",
        link=arrival_link,
        x=str(agent.get('vertiport_arrival_x', agent.get('dest_x', '0'))),
        y=str(agent.get('vertiport_arrival_y', agent.get('dest_y', '0'))),
        max_dur="00:00:01"
    )

    # Trip 4: passenger egress remains walk-only inside the destination site.
    ET.SubElement(plan, 'leg', mode="walk", routingMode="walk")
    ET.SubElement(
        plan,
        'activity',
        type="dummydestination",
        link=dest_link,
        x=str(agent.get('dest_x', '0')),
        y=str(agent.get('dest_y', '0'))
    )


def _append_direct_car_plan(plan, agent):
    """Append the complete origin-to-destination direct-car alternative."""
    orig_link = str(agent.get('origin_link_exact', agent.get('origin_link')))
    dest_link = str(agent.get('dest_link_exact', agent.get('dest_link')))

    ET.SubElement(
        plan,
        'activity',
        type="dummyorigin",
        link=orig_link,
        x=str(agent.get('origin_x', '0')),
        y=str(agent.get('origin_y', '0')),
        end_time=str(agent.get('departure_time', '0'))
    )
    ET.SubElement(plan, 'leg', mode="car", routingMode="car")
    ET.SubElement(
        plan,
        'activity',
        type="dummydestination",
        link=dest_link,
        x=str(agent.get('dest_x', '0')),
        y=str(agent.get('dest_y', '0'))
    )


def _append_scheduled_pt_plan(plan, agent):
    """Append an unrouted whole-journey PT alternative for SwissRailRaptor."""
    orig_link = str(agent.get("origin_link_exact", agent.get("origin_link")))
    dest_link = str(agent.get("dest_link_exact", agent.get("dest_link")))
    ET.SubElement(
        plan,
        "activity",
        type="dummyorigin",
        link=orig_link,
        x=str(agent.get("origin_x", "0")),
        y=str(agent.get("origin_y", "0")),
        end_time=str(agent.get("departure_time", "0")),
    )
    # The scheduled transit router expands this into access walk, rail, transfer
    # walk, bus, and egress walk stages from Module 3's timetable.
    ET.SubElement(plan, "leg", mode="pt", routingMode="pt")
    ET.SubElement(
        plan,
        "activity",
        type="dummydestination",
        link=dest_link,
        x=str(agent.get("dest_x", "0")),
        y=str(agent.get("dest_y", "0")),
    )

def write_matsim_network(nodes, links, output_path):
    """Generates a strict MATSim v2 network.xml file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    root = ET.Element('network')
    
    nodes_elem = ET.SubElement(root, 'nodes')
    for n in nodes:
        ET.SubElement(nodes_elem, 'node', id=str(n['id']), x=str(n['x']), y=str(n['y']))
        
    links_elem = ET.SubElement(root, 'links')
    for l in links:
        link_attrs = {
            'id': str(l['id']),
            'from': str(l['from']),  
            'to': str(l['to']),
            'length': str(l.get('length', 10.0)),
            'freespeed': str(l.get('freespeed', 13.8)),
            'capacity': str(l.get('capacity', 2000)),
            'permlanes': str(l.get('permlanes', 1.0)),
            'modes': str(l.get('modes', 'car'))
        }
        link_elem = ET.SubElement(links_elem, 'link', **link_attrs)
        
        if 'uam' in link_attrs['modes'] or 'flight' in link_attrs['modes']:
            attrs_elem = ET.SubElement(link_elem, 'attributes')
            attr = ET.SubElement(attrs_elem, 'attribute', name="type", **{"class": "java.lang.String"})
            attr.text = "flight"

    xmlstr = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
    xmlstr = xmlstr.split('\n', 1)[1] 

    final_xml = '<?xml version="1.0" encoding="utf-8"?>\n'
    final_xml += '<!DOCTYPE network SYSTEM "http://www.matsim.org/files/dtd/network_v2.dtd">\n'
    final_xml += xmlstr

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_xml)

def merge_matsim_network(base_network_path, nodes_list, links_list, output_path):
    """Merges UAM micro-topology into a pre-cleaned MATSim base network."""
    tree = ET.parse(base_network_path)
    root = tree.getroot()
    
    nodes_elem = root.find('nodes')
    for n in nodes_list:
        ET.SubElement(nodes_elem, 'node', id=str(n['id']), x=str(n['x']), y=str(n['y']))
        
    links_elem = root.find('links')
    for l in links_list:
        link_attrs = {
            'id': str(l['id']),
            'from': str(l['from']),  
            'to': str(l['to']),
            'length': str(l.get('length', 10.0)),
            'freespeed': str(l.get('freespeed', 13.8)),
            'capacity': str(l.get('capacity', 2000)),
            'permlanes': str(l.get('permlanes', 1.0)),
            'modes': str(l.get('modes', 'car'))
        }
        link_elem = ET.SubElement(links_elem, 'link', **link_attrs)
        
        if 'uam' in link_attrs['modes'] or 'flight' in link_attrs['modes']:
            attrs_elem = ET.SubElement(link_elem, 'attributes')
            attr = ET.SubElement(attrs_elem, 'attribute', name="type", **{"class": "java.lang.String"})
            attr.text = "flight"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    xmlstr = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
    xmlstr = xmlstr.split('\n', 1)[1] 

    final_xml = '<?xml version="1.0" encoding="utf-8"?>\n'
    final_xml += '<!DOCTYPE network SYSTEM "http://www.matsim.org/files/dtd/network_v2.dtd">\n'
    final_xml += xmlstr

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_xml)

def write_matsim_population(agents_list, output_path):
    """Generate MATSim v6 population.xml with UAM, car, and scheduled-PT plans."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    root = ET.Element('population')

    for agent in agents_list:
        person = ET.SubElement(root, 'person', id=agent['id'])

        if 'subpopulation' in agent:
            attrs = ET.SubElement(person, 'attributes')
            attr = ET.SubElement(attrs, 'attribute', name="subpopulation", **{"class": "java.lang.String"})
            attr.text = agent['subpopulation']

        # Eligibility is represented by retaining the UAM plan in every
        # passenger's choice set. The initially selected plan is controlled
        # separately to avoid forcing the entire eligible cohort onto UAM.
        initial_plan = str(agent.get("initial_plan", "uam")).lower()
        if initial_plan not in {"uam", "car", "pt"}:
            raise ValueError(
                f"Unknown initial_plan '{initial_plan}' for {agent['id']}."
            )
        if initial_plan == "pt" and not agent.get("pt_plan_enabled", True):
            raise ValueError(
                f"Passenger {agent['id']} starts on PT but has no PT plan."
            )

        uam_plan = ET.SubElement(
            person, 'plan', selected="yes" if initial_plan == "uam" else "no"
        )
        _append_multimodal_uam_plan(uam_plan, agent)

        car_plan = ET.SubElement(
            person, 'plan', selected="yes" if initial_plan == "car" else "no"
        )
        _append_direct_car_plan(car_plan, agent)

        if agent.get("pt_plan_enabled", True):
            pt_plan = ET.SubElement(
                person,
                "plan",
                selected="yes" if initial_plan == "pt" else "no",
            )
            _append_scheduled_pt_plan(pt_plan, agent)

    parsed_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
    parsed_str = parsed_str.split('\n', 1)[1]

    xml_str = '<?xml version="1.0" encoding="utf-8"?>\n'

    xml_str += '<!DOCTYPE population SYSTEM "http://www.matsim.org/files/dtd/population_v6.dtd" [\n'
    xml_str += '  <!ATTLIST leg routingMode CDATA #IMPLIED>\n'
    xml_str += ']>\n'

    xml_str += parsed_str

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml_str)

def merge_matsim_population(base_population_path, agents_list, output_path):
    """Merges UAM agents into background population."""
    if not os.path.exists(base_population_path):
        write_matsim_population(agents_list, output_path)
        return

    tree = ET.parse(base_population_path)
    root = tree.getroot()

    for ag in agents_list:
        person = ET.SubElement(root, "person", id=str(ag["id"]))

        attrs = ET.SubElement(person, "attributes")
        attr = ET.SubElement(attrs, "attribute", name="subpopulation", **{"class": "java.lang.String"})
        attr.text = ag["subpopulation"]

        initial_plan = str(ag.get("initial_plan", "uam")).lower()
        if initial_plan not in {"uam", "car", "pt"}:
            raise ValueError(
                f"Unknown initial_plan '{initial_plan}' for {ag['id']}."
            )
        if initial_plan == "pt" and not ag.get("pt_plan_enabled", True):
            raise ValueError(
                f"Passenger {ag['id']} starts on PT but has no PT plan."
            )

        uam_plan = ET.SubElement(
            person, "plan", selected="yes" if initial_plan == "uam" else "no"
        )
        _append_multimodal_uam_plan(uam_plan, ag)

        car_plan = ET.SubElement(
            person, "plan", selected="yes" if initial_plan == "car" else "no"
        )
        _append_direct_car_plan(car_plan, ag)

        if ag.get("pt_plan_enabled", True):
            pt_plan = ET.SubElement(
                person,
                "plan",
                selected="yes" if initial_plan == "pt" else "no",
            )
            _append_scheduled_pt_plan(pt_plan, ag)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    xmlstr = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
    xmlstr = xmlstr.split('\n', 1)[1]

    final_xml = '<?xml version="1.0" encoding="utf-8"?>\n'
    final_xml += '<!DOCTYPE population SYSTEM "http://www.matsim.org/files/dtd/population_v6.dtd" [\n'
    final_xml += '  <!ATTLIST leg routingMode CDATA #IMPLIED>\n'
    final_xml += ']>\n'
    final_xml += xmlstr

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_xml)

def writematsimvehicles(stations_list, vehicle_type, vehicles_list, outputpath):
    """
    Generates the exact UAM fleet schema required by UAMXMLReader.java.
    Uses the strictly required lowercase attribute names and creates the mandatory <vehicleType> tag.
    """
    root = ET.Element('uamVehicles')

    required_vehicle_fields = {
        "id",
        "capacity",
        "range",
        "cruise_speed",
        "vertical_speed",
        "boarding_time",
        "deboarding_time",
        "turnaround_time",
        "maximum_charge",
        "energy_consumption_vertical",
        "energy_consumption_horizontal",
    }
    missing_fields = sorted(required_vehicle_fields - set(vehicle_type))
    if missing_fields:
        raise ValueError(f"UAM_VEHICLE_TYPE is missing: {', '.join(missing_fields)}")

    # 1. Parameterise Vertiport Stations
    for station in stations_list:
        preflight_time = float(
            station.get('t_process', vehicle_type['boarding_time'])
        )
        if preflight_time <= 0.0:
            raise ValueError(
                f"UAM station {station['id']} requires a positive t_process."
            )
        
        # --- CRITICAL FIX: Ensure eVTOL fleet parks exactly on the pad links generated in Module 1 ---
        ET.SubElement(root, 'station', 
            id=str(station['id']), 
            name=str(station['id']),
            link=f"link_stand_apron_{station['id']}",
            # This is the single authoritative passenger-processing duration.
            # Terminal network links contain walking time only.
            preflighttime=str(preflight_time),
            postflighttime=str(float(vehicle_type['deboarding_time'])),
            defaultwaittime=str(float(vehicle_type['boarding_time'])),
            numberOfChargers="4",       # Mandatory based on Java source
            chargingSpeed="100.0"       # Mandatory based on Java source
        )

    # 2. Parameterise the Universal Vehicle Type (Required by Java source)
    ET.SubElement(root, 'vehicleType',
        id=str(vehicle_type['id']),
        capacity=str(int(vehicle_type['capacity'])),
        range=str(float(vehicle_type['range'])),
        cruisespeed=str(float(vehicle_type['cruise_speed'])),
        verticalspeed=str(float(vehicle_type['vertical_speed'])),
        boardingtime=str(float(vehicle_type['boarding_time'])),
        deboardingtime=str(float(vehicle_type['deboarding_time'])),
        turnaroundtime=str(float(vehicle_type['turnaround_time'])),
        maximumCharge=str(float(vehicle_type['maximum_charge'])),
        energyConsumptionVertical=str(float(vehicle_type['energy_consumption_vertical'])),
        energyConsumptionHorizontal=str(float(vehicle_type['energy_consumption_horizontal']))
    )

    # 3. Parameterise Physical eVTOL Fleet
    for veh in vehicles_list:
        station_id = str(veh.get('station_id', veh.get('location', '')))
        
        # The vehicle tag only requires ID, type, scheduling, and location
        ET.SubElement(root, 'vehicle', 
            id=str(veh['id']), 
            type=str(veh['type']),
            starttime="0.0",
            endtime="86400.0",
            initialstation=station_id
        ) 

    # 4. Format and Export XML (Clean, no DTD required)
    os.makedirs(os.path.dirname(outputpath), exist_ok=True)
    xmlstr = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
    
    parsed_str = xmlstr.split('\n', 1)[1] if xmlstr.startswith('<?xml') else xmlstr
    final_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + parsed_str.strip()

    with open(outputpath, 'w', encoding='utf-8') as f:
        f.write(final_xml)

    print(f"[XML Writer] Successfully saved precise UAM fleet and stations to {outputpath}")

def writematsimconfig(configparams, outputpath):
    """Generates the master MATSim config.xml file."""
    xml_str = "<?xml version=\"1.0\" encoding=\"utf-8\" ?>\n"
    xml_str += "<!DOCTYPE config SYSTEM \"http://www.matsim.org/files/dtd/config_v2.dtd\">\n"
    xml_str += "<config>\n"

    # --- Core Modules ---
    xml_str += "\t<module name=\"global\" >\n"
    xml_str += (
        "\t\t<param name=\"randomSeed\" "
        f"value=\"{int(configparams.get('random_seed', 4711))}\" />\n"
    )
    xml_str += "\t</module>\n"

    xml_str += "\t<module name=\"network\" >\n"
    xml_str += f"\t\t<param name=\"inputNetworkFile\" value=\"{configparams['networkfile']}\" />\n"
    xml_str += "\t</module>\n"

    xml_str += "\t<module name=\"plans\" >\n"
    xml_str += f"\t\t<param name=\"inputPlansFile\" value=\"{configparams['populationfile']}\" />\n"
    xml_str += "\t\t<param name=\"handlingOfPlansWithoutRoutingMode\" value=\"useMainModeIdentifier\" />\n"
    xml_str += "\t</module>\n"

    xml_str += "\t<module name=\"controler\" >\n"
    xml_str += f"\t\t<param name=\"outputDirectory\" value=\"{configparams['outputdir']}\" />\n"
    xml_str += "\t\t<param name=\"firstIteration\" value=\"0\" />\n"
    xml_str += f"\t\t<param name=\"lastIteration\" value=\"{configparams['iterations']}\" />\n"
    xml_str += "\t\t<param name=\"eventsFileFormat\" value=\"xml\" />\n"
    xml_str += (
        "\t\t<param name=\"writePlansInterval\" "
        f"value=\"{configparams.get('write_plans_interval', 10)}\" />\n"
    )
    xml_str += "\t\t<param name=\"routingAlgorithmType\" value=\"SpeedyALT\" />\n"
    xml_str += "\t</module>\n"

    xml_str += "\t<module name=\"qsim\" >\n"
    xml_str += "\t\t<param name=\"endTime\" value=\"30:00:00\" />\n"
    xml_str += "\t\t<param name=\"simStarttimeInterpretation\" value=\"onlyUseStarttime\" />\n"
    xml_str += "\t</module>\n"

 #-------------------------------------------------------------------------------------------
    xml_str += "\t<module name=\"routing\" >\n"
    xml_str += "\t\t<param name=\"routingRandomness\" value=\"0.0\" />\n"
    xml_str += "\t</module>\n"
 #--------------------------------------------------------------------------------------------

    # --- Scheduled public transport generated by Module 3 ---
    transit_routing = configparams.get("transit_routing", {})
    xml_str += "\t<module name=\"transit\" >\n"
    xml_str += (
        "\t\t<param name=\"transitScheduleFile\" "
        f"value=\"{configparams['transit_schedule_file']}\" />\n"
    )
    xml_str += (
        "\t\t<param name=\"vehiclesFile\" "
        f"value=\"{configparams['transit_vehicles_file']}\" />\n"
    )
    xml_str += "\t\t<param name=\"useTransit\" value=\"true\" />\n"
    xml_str += "\t\t<param name=\"usingTransitInMobsim\" value=\"true\" />\n"
    xml_str += "\t\t<param name=\"transitModes\" value=\"pt\" />\n"
    xml_str += (
        "\t\t<param name=\"routingAlgorithmType\" "
        f"value=\"{transit_routing.get('algorithm', 'SwissRailRaptor')}\" />\n"
    )
    xml_str += "\t</module>\n"

    xml_str += "\t<module name=\"transitRouter\" >\n"
    xml_str += (
        "\t\t<param name=\"searchRadius\" "
        f"value=\"{transit_routing.get('search_radius_m', 1500.0)}\" />\n"
    )
    xml_str += (
        "\t\t<param name=\"extensionRadius\" "
        f"value=\"{transit_routing.get('extension_radius_m', 200.0)}\" />\n"
    )
    xml_str += (
        "\t\t<param name=\"maxBeelineWalkConnectionDistance\" "
        f"value=\"{transit_routing.get('max_walk_connection_distance_m', 1000.0)}\" />\n"
    )
    xml_str += (
        "\t\t<param name=\"additionalTransferTime\" "
        f"value=\"{transit_routing.get('additional_transfer_time_s', 0.0)}\" />\n"
    )
    xml_str += "\t</module>\n"

    # --- Full Subpopulation Scoring Block ---
    xml_str += "\t<module name=\"planCalcScore\" >\n"
    xml_str += "\t\t<param name=\"learningRate\" value=\"1.0\" />\n"
    xml_str += "\t\t<param name=\"BrainExpBeta\" value=\"2.0\" />\n"
    write_experienced_plans = str(
        configparams.get("write_experienced_plans", False)
    ).lower()
    xml_str += (
        "\t\t<param name=\"writeExperiencedPlans\" "
        f"value=\"{write_experienced_plans}\" />\n"
    )

    subpopulations = [
        {"name": "high_urgency", "wait": configparams.get('betawaithigh', -24.0)},
        {"name": "low_urgency", "wait": configparams.get('betawaitlow', -12.0)},
        {"name": "default", "wait": -12.0} 
    ]

    for sp in subpopulations:
        xml_str += "\t\t<parameterset type=\"scoringParameters\" >\n"
        xml_str += f"\t\t\t<param name=\"subpopulation\" value=\"{sp['name']}\" />\n"
            
        xml_str += "\t\t\t<param name=\"earlyDeparture\" value=\"-0.0\" />\n"
        xml_str += "\t\t\t<param name=\"lateArrival\" value=\"-18.0\" />\n"
        xml_str += "\t\t\t<param name=\"marginalUtilityOfMoney\" value=\"1.0\" />\n"
        xml_str += "\t\t\t<param name=\"performing\" value=\"6.0\" />\n"
        xml_str += (
            "\t\t\t<param name=\"utilityOfLineSwitch\" "
            f"value=\"{configparams.get('utility_of_line_switch', -1.0)}\" />\n"
        )
        xml_str += f"\t\t\t<param name=\"waiting\" value=\"{sp['wait']}\" />\n"
        xml_str += f"\t\t\t<param name=\"waitingPt\" value=\"{sp['wait']}\" />\n"

        activities = [
            ("dummyorigin", "01:00:00", "true"),
            ("dummydestination", "01:00:00", "true"),
            ("vertiport_entry", "00:00:01", "false"),
            ("vertiport_boarding", "00:00:01", "false"),
            ("vertiport_arrival", "00:00:01", "false"),
            ("vertiport_interaction", "01:00:00", "false"),
            ("uam_interaction", "undefined", "false"),
            ("uam_terminal_wait", "undefined", "false"),
            ("car interaction", "undefined", "false"),
            ("walk interaction", "undefined", "false"),
            ("pt interaction", "undefined", "false"),
            ("access_uam_walk interaction", "undefined", "false"),
            ("egress_uam_walk interaction", "undefined", "false"),
            ("access_uam_car interaction", "undefined", "false"),
            ("egress_uam_car interaction", "undefined", "false")
        ]
        
        for act, dur, score in activities:
            xml_str += "\t\t\t<parameterset type=\"activityParams\" >\n"
            xml_str += f"\t\t\t\t<param name=\"activityType\" value=\"{act}\" />\n"
            xml_str += f"\t\t\t\t<param name=\"typicalDuration\" value=\"{dur}\" />\n"
            xml_str += f"\t\t\t\t<param name=\"scoringThisActivityAtAll\" value=\"{score}\" />\n"
            xml_str += "\t\t\t</parameterset>\n"
            
        modes = [
            "walk",
            "pt",
            "car",
            "uam",
            "access_uam_walk",
            "egress_uam_walk",
            "access_uam_car",
            "egress_uam_car",
            "teleport_car"
        ]
        for mode in modes:
            xml_str += "\t\t\t<parameterset type=\"modeParams\" >\n"
            xml_str += f"\t\t\t\t<param name=\"mode\" value=\"{mode}\" />\n"
            xml_str += "\t\t\t\t<param name=\"constant\" value=\"0.0\" />\n"
            xml_str += f"\t\t\t\t<param name=\"marginalUtilityOfTraveling_util_hr\" value=\"{configparams.get('betatravel', -6.0)}\" />\n"
            xml_str += "\t\t\t\t<param name=\"monetaryDistanceRate\" value=\"0.0\" />\n"
            xml_str += "\t\t\t</parameterset>\n"
            
        xml_str += "\t\t</parameterset>\n" 
        
    xml_str += "\t</module>\n"

    # --- Strategy Parameters (Refactored for Multi-Subpopulation Support) ---
    xml_str += "\t<module name=\"replanning\" >\n"
    xml_str += f"\t\t<param name=\"maxAgentPlanMemorySize\" value=\"{configparams['memory']}\" />\n"
    xml_str += (
        "\t\t<param name=\"fractionOfIterationsToDisableInnovation\" "
        f"value=\"{configparams.get('innovation_disable_fraction', 0.80)}\" />\n"
    )
    
    # Loop over each subpopulation and print distinct parameter sets
    for subpop, strategy_set in configparams['strategies_by_subpop'].items():
        for name, weight in strategy_set.items():
            if weight > 0.0:
                xml_str += "\t\t<parameterset type=\"strategysettings\" >\n"
                xml_str += f"\t\t\t<param name=\"strategyName\" value=\"{name}\" />\n"
                xml_str += f"\t\t\t<param name=\"weight\" value=\"{weight}\" />\n"
                xml_str += f"\t\t\t<param name=\"subpopulation\" value=\"{subpop}\" />\n"
                xml_str += "\t\t</parameterset>\n"
                
    xml_str += "\t</module>\n"

    # --- UAM Extension Parameters ---
    xml_str += "\t<module name=\"uam\" >\n"
    xml_str += f"\t\t<param name=\"inputFile\" value=\"{configparams['vehiclesfile']}\" />\n"
    access_egress_modes = configparams.get('uam_access_egress_modes', ('walk',))
    if isinstance(access_egress_modes, str):
        access_egress_modes = [mode.strip() for mode in access_egress_modes.split(',')]
    xml_str += f"\t\t<param name=\"accessEgressModes\" value=\"{','.join(access_egress_modes)}\" />\n"
    xml_str += "\t\t<param name=\"routingStrategy\" value=\"MINACCESSTRAVELTIME\" />\n"
    xml_str += f"\t\t<param name=\"searchRadius\" value=\"{configparams.get('uam_search_radius', 15000.0)}\" />\n"
    xml_str += f"\t\t<param name=\"maxPoolingWaitTime\" value=\"{configparams.get('uam_max_pooling_wait_time', 300.0)}\" />\n"
    xml_str += "\t\t<param name=\"walkDistance\" value=\"500.0\" />\n"
    xml_str += "\t\t<param name=\"useCharging\" value=\"false\" />\n"
    xml_str += "\t\t<param name=\"useDynamicSearchRadius\" value=\"false\" />\n"
    xml_str += "\t</module>\n"



    # --- VSP Experimental ---
    if 'vspExperimental' in configparams:
        xml_str += "\t<module name=\"vspExperimental\" >\n"
        for key, value in configparams['vspExperimental'].items():
            xml_str += f"\t\t<param name=\"{key}\" value=\"{value}\" />\n"
        xml_str += "\t</module>\n"

    xml_str += "</config>\n"

    os.makedirs(os.path.dirname(outputpath), exist_ok=True)
    with open(outputpath, 'w', encoding='utf-8') as f:
        f.write(xml_str)
