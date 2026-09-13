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
    legacy = sorted(old-new)
    legacy_references = {n: [k for k in a.namelist() if k.endswith('.class') and k not in legacy and n[:-6].encode() in a.read(k)] for n in legacy}
    dependency_classes = {n for n in a.namelist() if n.endswith('.class') and n not in old}
    rebuilt_dependency_classes = {n for n in b.namelist() if n.endswith('.class') and n not in new}
    dependency_differences = [n for n in sorted(dependency_classes & rebuilt_dependency_classes) if a.read(n) != b.read(n)]
    dependency_missing = sorted(dependency_classes-rebuilt_dependency_classes)
    dependency_extra = sorted(rebuilt_dependency_classes-dependency_classes)
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
result = {'original_sha256': digest(original), 'rebuilt_sha256': digest(rebuilt), 'original_application_classes': len(old), 'rebuilt_application_classes': len(new), 'byte_identical_application_classes': len(common)-len(different), 'missing_classes': sorted(old-new), 'extra_classes': sorted(new-old), 'disassembly_differences': differences, 'dtd_resource_differences': resource_differences, 'legacy_class_references': legacy_references, 'dependency_class_count': len(dependency_classes), 'dependency_class_byte_differences': dependency_differences, 'missing_dependency_classes': dependency_missing, 'extra_dependency_classes': dependency_extra, 'comparison_scope': 'All net/bhl/matsim/uam classes; normalized javap instructions/signatures/constants for byte-different classes. This is not proof of complete shaded dependency equivalence.'}
(output/'java-comparison.json').write_text(json.dumps(result, indent=2))
(output/'bundled-dependencies.json').write_text(json.dumps({'original': inventory(original), 'rebuilt': inventory(rebuilt)}, indent=2))
print(json.dumps(result, indent=2))

# Known stale classes may be absent only when no retained class references them.
expected_legacy = {
    'net/bhl/matsim/uam/scoring/UAMScoringFunctionFactory$PostBoardingQueueScoring.class',
    'net/bhl/matsim/uam/scoring/UAMScoringFunctionFactory$VertiportWaitingScoring.class',
}
result['application_code_matches'] = (
    not result['extra_classes'] and not result['disassembly_differences']
    and set(result['missing_classes']).issubset(expected_legacy)
    and not any(result['legacy_class_references'].values())
)
(output/'java-comparison.json').write_text(json.dumps(result, indent=2))
print(json.dumps({'application_code_matches':result['application_code_matches'],'legacy_class_references':legacy_references,'dependency_class_byte_differences':dependency_differences,'missing_dependency_classes':dependency_missing,'extra_dependency_classes':dependency_extra},indent=2))
