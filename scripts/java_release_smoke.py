"""Run both release and rebuilt JARs against deterministic, synthetic no-PT scenarios."""
from pathlib import Path
from collections import Counter
import copy
import gzip
import hashlib
import json
import math
import pprint
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

archive, rebuilt, work, evidence = map(lambda x: Path(x).resolve(), sys.argv[1:])
work.mkdir(parents=True, exist_ok=True)
evidence.mkdir(parents=True, exist_ok=True)
results = {}
for runtime in ('original', 'rebuilt'):
    for disabled in (False, True):
        name = runtime + ('-disabled' if disabled else '-empty')
        case = work/name
        with zipfile.ZipFile(archive) as z:
            z.extractall(case)
        kit = case/'UST-Toolkit-v1.0.1'
        jar = kit/'lib/matsim-uam-5.0.0.jar'
        if runtime == 'rebuilt':
            shutil.copyfile(rebuilt, jar)
        network = ET.Element('network')
        nodes = ET.SubElement(network, 'nodes')
        links = ET.SubElement(network, 'links')
        coordinates = {}
        for row in range(2):
            for col in range(3):
                node = f'n{row}_{col}'
                coordinates[node] = (530000+5000*col, 180000+1000*row)
                ET.SubElement(nodes, 'node', id=node, x=str(coordinates[node][0]), y=str(coordinates[node][1]))
        for row in range(2):
            for col in range(3):
                start = f'n{row}_{col}'
                adjacent = ([f'n{row}_{col+1}'] if col < 2 else []) + ([f'n{row+1}_{col}'] if row == 0 else [])
                for end in adjacent:
                    for a,b in ((start,end),(end,start)):
                        ET.SubElement(links, 'link', id=a+'_'+b, **{'from':a,'to':b,'length':str(math.dist(coordinates[a],coordinates[b])),'freespeed':'15','capacity':'1800','permlanes':'1','modes':'car'})
        ET.ElementTree(network).write(kit/'data/base_network.xml', encoding='utf-8', xml_declaration=True)
        template = json.loads((kit/'tests/fixtures/vertiport.json').read_text())
        vertiports = []
        for i,x in ((1,530000),(2,540000)):
            v = copy.deepcopy(template)
            v.update(id=str(i),name=f'Synthetic {i}',x=x,y=180000,t_sep=60,t_process=30)
            v['layout']['stands']['count']=2
            vertiports.append(v)
        events = []
        for i,(a,b) in enumerate(((vertiports[0],vertiports[1]),(vertiports[1],vertiports[0]))):
            events.append(dict(source_name=f'synthetic_{i}',origin_x=a['x'],origin_y=a['y'],dest_x=b['x'],dest_y=b['y'],vertiport_id=a['id'],dest_vertiport_id=b['id'],access_mode='car',flight_mode='uam',t_event=28800+600*i,c_source=6,uam_adoption=1.0,initial_uam_count=4,initial_ground_plan='car',release_delay_mean_s=30,release_delay_std_s=5,high_urgency_ratio=0.5))
        settings = dict(SCENARIO_NAME='synthetic_java_build_validation',MODULE5_CRS='EPSG:27700',NITER=1,WRITE_PLANS_INTERVAL=1,FLEET_SIZE=4,DEMAND_RANDOM_SEED=42,VERTIPORTS=vertiports,AERIAL_ROUTES=[dict(from_vertiport='1',to_vertiport='2',bidirectional=True)],DEMAND_EVENTS=events,MODULE5_AUTO_LAUNCH=False,TRANSPORT_SUPPLY=dict(enabled=not disabled,trains=[],buses=[]))
        with (kit/'src/config.py').open('a') as config:
            config.write('\n# Isolated synthetic Java build validation.\n')
            for key,value in settings.items():
                config.write(key+' = '+pprint.pformat(value)+'\n')
            config.write('UAM_VEHICLE_TYPE = {**UAM_VEHICLE_TYPE, "capacity": 2, "boarding_time": 30.0, "deboarding_time": 15.0, "turnaround_time": 60.0}\n')
        with (evidence/(name+'.log')).open('w') as log:
            subprocess.run([sys.executable,'src/pipeline.py','--check'],cwd=kit,stdout=log,stderr=subprocess.STDOUT,check=True)
            subprocess.run([sys.executable,'-u','src/pipeline.py'],cwd=kit,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
        population = ET.parse(kit/'scenarios/populations/population.xml').getroot()
        people = {p.get('id') for p in population.findall('person')}
        assert len(people)==12 and not population.findall('.//leg[@mode="pt"]')
        iterations = {}
        for iteration in (0,1):
            arrived = set(); counts = Counter()
            with gzip.open(kit/f'outputs/ITERS/it.{iteration}/{iteration}.events.xml.gz','rb') as stream:
                for _,event in ET.iterparse(stream,events=('end',)):
                    if event.tag != 'event': continue
                    a=event.attrib; kind=a['type']; counts[kind]+=1
                    if kind=='actstart' and a.get('actType')=='dummydestination': arrived.add(a.get('person'))
                    event.clear()
            assert arrived==people
            assert not any(count for kind,count in counts.items() if 'stuck' in kind.lower())
            assert counts['passenger picked up']==counts['passenger dropped off']>0
            assert counts['uam pre-boarding wait']>0 and counts['uam post-boarding queue']>0
            iterations[str(iteration)]={'arrived':len(arrived),'uam_pickups':counts['passenger picked up'],'uam_dropoffs':counts['passenger dropped off'],'stuck':0}
        analytics=json.loads((kit/'outputs/module5_analytics/analytics_bundle.json').read_text())
        outcome=analytics['outcomes']
        assert outcome['eligibleTravellers']==12 and outcome['unobserved']==0 and outcome['ptSelected']==0
        results[name]={'jar_sha256':hashlib.sha256(jar.read_bytes()).hexdigest(),'iterations':iterations,'outcomes':outcome}
        (evidence/'smoke-results.json').write_text(json.dumps(results,indent=2))
        print(name, json.dumps(iterations), flush=True)
for mode in ('empty','disabled'):
    assert results['original-'+mode]['iterations']==results['rebuilt-'+mode]['iterations']
    assert results['original-'+mode]['outcomes']==results['rebuilt-'+mode]['outcomes']
print('PASS: original and rebuilt runtimes complete both no-PT scenarios with matching recorded outcomes.')
