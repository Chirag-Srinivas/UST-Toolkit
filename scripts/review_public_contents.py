"""Inventory tracked/history/release content without printing candidate secret values."""
from pathlib import Path
import hashlib
import io
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

archive, output = map(Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
patterns = {
    'private-key': rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    'github-token': rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b',
    'aws-access-id': rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'slack-token': rb'\bxox[baprs]-[A-Za-z0-9-]{20,}\b',
    'openai-key': rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{40,}\b',
}
def scan(data):
    return [name for name,pattern in patterns.items() if re.search(pattern,data)]
history = subprocess.check_output(['git','rev-list','--objects','--all'],text=True).splitlines()
suspect = []; scanned = 0; history_paths = []; seen = set()
for line in history:
    parts=line.split(' ',1)
    if len(parts)!=2: continue
    oid,path=parts
    if subprocess.check_output(['git','cat-file','-t',oid],text=True).strip()!='blob': continue
    history_paths.append(path)
    if oid in seen: continue
    seen.add(oid); scanned+=1
    data=subprocess.check_output(['git','cat-file','blob',oid])
    hits=scan(data)
    if hits:suspect.append({'scope':'git-history','path':path,'patterns':hits})
forbidden=[p for p in history_paths if p.lower().endswith(('.zip','.jar','.p12','.pfx','.pem','.key')) or Path(p).name=='.env']
with zipfile.ZipFile(archive) as release:
    names=release.namelist()
    file_rows=[]
    for name in names:
        if name.endswith('/'):continue
        data=release.read(name)
        hits=scan(data)
        if hits:suspect.append({'scope':'release','path':name,'patterns':hits})
        file_rows.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    jarname=next(n for n in names if n.endswith('/lib/matsim-uam-5.0.0.jar'))
    with zipfile.ZipFile(io.BytesIO(release.read(jarname))) as jar:
        poms=[]; ns={'m':'http://maven.apache.org/POM/4.0.0'}
        for name in jar.namelist():
            if name.startswith('META-INF/maven/') and name.endswith('/pom.xml'):
                p=ET.fromstring(jar.read(name))
                poms.append({'path':name,'licenses':[{c.tag.split('}')[-1]:c.text for c in e} for e in p.findall('m:licenses/m:license',ns)]})
        notices=[n for n in jar.namelist() if re.search(r'(^|/)(LICENSE|NOTICE|COPYING)',n,re.I)]
        (output/'runtime-notices.json').write_text(json.dumps({'embedded_poms':poms,'notice_paths':notices},indent=2))
result={'unique_history_blobs_scanned':scanned,'suspicious_secret_patterns':suspect,'forbidden_history_file_paths':sorted(set(forbidden)),'release_file_count':len(file_rows),'release_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'release_archives':[n for n in names if n.lower().endswith(('.zip','.7z','.rar'))],'release_runtime_files':[n for n in names if n.endswith('.jar')],'limitations':'Pattern scan, not a guarantee against every secret format. Upstream test-data and dependency attribution are reviewed separately.'}
(output/'public-content-review.json').write_text(json.dumps(result,indent=2))
(output/'release-file-inventory.json').write_text(json.dumps(file_rows,indent=2))
print(json.dumps(result,indent=2))
assert not suspect and not forbidden and not result['release_archives']
