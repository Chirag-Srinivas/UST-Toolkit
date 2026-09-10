# Download the exact prepared runtime

For normal use, download **UST-Toolkit-v1.0.0.zip** from the
[prepared toolkit prerelease](https://github.com/Chirag-Srinivas/UST-Toolkit/releases/tag/v1.0.0-prepared).
The repository is private, so sign in with an account that has access.

**Known prerelease issue:** the documented UAM/car-only configuration with
empty train/bus lists currently fails in Module 3, even though `--check`
reports success. A small run with a configured bus service passed. See the
[fresh-install validation report](FRESH-INSTALL-VALIDATION.md); do not add
fictional transport services to a study merely to bypass this defect.

This bundle includes the exact modified `lib/matsim-uam-5.0.0.jar`, the edited
Java source and POM, resources/DTD, Python toolkit, compiled dashboard, licences
and documentation. You do not need to apply the patch or rebuild Java to use
the supplied runtime. GitHub's automatic **Source code (zip)** download and a
Git clone contain source only and do not include the JAR.

## Verify and extract

Download `UST-Toolkit-v1.0.0.zip` and `SHA256SUMS-toolkit.txt` from the release.
The ZIP is 91,563,321 bytes. Its SHA-256 is:

```text
8aff19d9b70cc62c5829ff16753dd5ba0fac4353e69012fa5e0adb5ced3457d0
```

In PowerShell, run this in the download folder and compare the result:

```powershell
Get-FileHash .\UST-Toolkit-v1.0.0.zip -Algorithm SHA256
Expand-Archive .\UST-Toolkit-v1.0.0.zip -DestinationPath .\UST-download
cd .\UST-download\UST-Toolkit-v1.0.0
Get-FileHash .\lib\matsim-uam-5.0.0.jar -Algorithm SHA256
```

The JAR is 89,310,293 bytes. Its SHA-256 must be:

```text
df139dc1ad847888ab55ffad74960ee022000b7b5afa51d7ae712443a463db4b
```

On Linux use `sha256sum`; on macOS use `shasum -a 256` to check the same files.
Keep the extracted directory structure intact.

## Start a fresh scenario

Install **Java 21** and **Python 3.11 or newer** (the recorded validation used
Python 3.12). From the extracted toolkit directory, on Windows:

```powershell
py -3.12 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Supply your own network at `data/base_network.xml` and configure the network
CRS, vertiports, routes, demand and fleet in `src/config.py`. Follow
[the scenario setup guide](../experiment_inputs/README.md). Then run:

```powershell
.\venv\Scripts\python.exe src/pipeline.py --check
.\venv\Scripts\python.exe src/pipeline.py
```

An unconfigured fresh download will report missing inputs. It is not a
preconfigured research simulation. Node.js and Maven are not required when
using the supplied compiled dashboard and runtime.

If you already cloned the source repository, copy the bundle's
`lib/matsim-uam-5.0.0.jar` into your checkout's `lib` directory, verify its hash,
and follow the same setup steps. The JAR remains ignored by Git.

## What the checks establish

The bundle preserves the exact recorded working executable for MATSim 2024.0
and UAM Extension 5.0.0. All 497 manifest-listed files were read back and their
sizes and SHA-256 hashes matched before upload. The release includes the file
manifest. This confirms file identity, not a clean rebuild of the JAR from the
supplied source or validation of every historical simulation. See
[runtime provenance](../lib/MATSim/PROVENANCE.json) and
[validation limits](VALIDATION.md).

The ZIP is the unchanged prepared snapshot; its internal preparation notes
describe the state before upload. This guide and the release notes record the
download status. The 34.56 GB MSc archive is separate and is not included in
this bundle or Git history.
