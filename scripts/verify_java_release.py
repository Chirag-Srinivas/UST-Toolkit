"""Compare rebuilt application code with the published runtime and inventory dependencies."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import difflib
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

original, rebuilt, output = map(Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def disassemble(jar, name):
    result = subprocess.run(['javap', '-classpath', str(jar), '-c', '-p', '-s', '-constants', name[:-6].replace('/', '.')], capture_output=True, text=True, check=True)
    # Keep opcodes, branch targets, constants and symbolic comments; ignore CP indices.
    return re.sub(r'#\d+', '#CP', result.stdout).splitlines(keepends=True)
def inventory(jar):
    with zipfile.ZipFile(jar) as z:
        poms = []
        for name in z.namelist():
            if name.startswith('META-INF/maven/') and name.endswith('/pom.xml'):
                root = ET.fromstring(z.read(name))
                ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
                poms.append({'path': name, 'licenses': [{c.tag.split('}')[-1]: c.text for c in license} for license in root.findall('m:licenses/m:license', ns)]})
        return {'sha256': digest(jar), 'bytes': jar.stat().st_size, 'embedded_poms': poms, 'notice_files': [n for n in z.namelist() if re.search(r'(^|/)(LICENSE|NOTICE|COPYING)', n, re.I)]}
with zipfile.ZipFile(original) as a, zipfile.ZipFile(rebuilt) as b:
    classes = lambda z: {n for n in z.namelist() if n.startswith('net/bhl/matsim/uam/') and n.endswith('.class')}
    old, new = classes(a), classes(b)
    common = sorted(old & new)
    different = [n for n in common if a.read(n) != b.read(n)]
    resources = [n for n in a.namelist() if n.startswith('dtd/')]
    resource_differences = [n for n in resources if n not in b.namelist() or a.read(n) != b.read(n)]
def compare(name):
    before, after = disassemble(original, name), disassemble(rebuilt, name)
    if before == after:
        return None
    patch = ''.join(difflib.unified_diff(before, after, fromfile='original/'+name, tofile='rebuilt/'+name))
    (output / (name.replace('/', '_')+'.diff')).write_text(patch)
    return name
with ThreadPoolExecutor(max_workers=4) as executor:
    differences = [n for n in executor.map(compare, different) if n]
result = {'original_sha256': digest(original), 'rebuilt_sha256': digest(rebuilt), 'original_application_classes': len(old), 'rebuilt_application_classes': len(new), 'byte_identical_application_classes': len(common)-len(different), 'missing_classes': sorted(old-new), 'extra_classes': sorted(new-old), 'disassembly_differences': differences, 'dtd_resource_differences': resource_differences, 'comparison_scope': 'All net/bhl/matsim/uam classes; normalized javap instructions/signatures/constants for byte-different classes. This is not proof of complete shaded dependency equivalence.'}
(output/'java-comparison.json').write_text(json.dumps(result, indent=2))
(output/'bundled-dependencies.json').write_text(json.dumps({'original': inventory(original), 'rebuilt': inventory(rebuilt)}, indent=2))
print(json.dumps(result, indent=2))
