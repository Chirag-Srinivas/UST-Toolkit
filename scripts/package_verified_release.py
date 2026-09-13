"""Package tracked toolkit files and the independently verified runtime."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import subprocess
import sys
import zipfile

runtime = Path(sys.argv[1])
destination = Path(sys.argv[2])
destination.mkdir(parents=True, exist_ok=True)
version = '1.0.2'
prefix = f'UST-Toolkit-v{version}'
provenance = json.loads(Path('lib/MATSim/PROVENANCE.json').read_text())
jar_bytes = runtime.read_bytes()
assert hashlib.sha256(jar_bytes).hexdigest() == provenance['runtimeSha256']
assert len(jar_bytes) == provenance['runtimeBytes']
tracked = subprocess.check_output(['git','ls-files','-z']).decode().strip('\0').split('\0')
files = {}
for name in tracked:
    path = PurePosixPath(name)
    assert not path.is_absolute() and '..' not in path.parts
    assert path.suffix.lower() not in {'.jar','.zip','.7z','.pem','.p12','.pfx','.key'}
    assert not any(p in {'.git','node_modules','venv','.venv','__pycache__'} for p in path.parts)
    assert path.name != '.env'
    assert not Path(name).is_symlink()
    files[name] = Path(name).read_bytes()
files['lib/matsim-uam-5.0.0.jar'] = jar_bytes
manifest = {
    'version': version,
    'sourceCommit': subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),
    'javaVerificationCommit': provenance['cleanBuild']['sourceCommit'],
    'javaVerificationRun': provenance['cleanBuild']['workflowRun'],
    'files': [{'path': p, 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()} for p,b in sorted(files.items())]
}
files['RELEASE-MANIFEST.json'] = (json.dumps(manifest,indent=2)+'\n').encode()
archive = destination / (prefix+'.zip')
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name,data in sorted(files.items()):
        info = zipfile.ZipInfo(prefix+'/'+name, (2026,9,13,0,0,0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        z.writestr(info,data)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert len(z.namelist()) == len(files)
    for name,data in files.items():
        assert z.read(prefix+'/'+name) == data, name
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(destination/'SHA256SUMS-toolkit.txt').write_text(digest+'  '+archive.name+'\n')
(destination/'RELEASE-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'archive':archive.name,'bytes':archive.stat().st_size,'sha256':digest,'files':len(files)},indent=2))
