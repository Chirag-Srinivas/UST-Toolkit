# Download the exact prepared runtime

For normal use, download **UST-Toolkit-v1.0.2.zip** from the
[prepared toolkit prerelease](https://github.com/Chirag-Srinivas/UST-Toolkit/releases/tag/v1.0.2-prepared).
The repository is private, so sign in with an account that has access.

Version 1.0.2 supplies the verified clean Java build and includes the 1.0.1
correction for empty or disabled PT. See [Java build validation](JAVA-BUILD-VALIDATION.md)
and [no-PT fix validation](OPTIONAL-TRANSPORT-FIX.md).

This bundle includes the exact modified `lib/matsim-uam-5.0.0.jar`, the edited
Java source and POM, resources/DTD, Python toolkit, compiled dashboard, licences
and documentation. You do not need to apply the patch or rebuild Java to use
the supplied runtime. GitHub's automatic **Source code (zip)** download and a
Git clone contain source only and do not include the JAR.

## Verify and extract

Download `UST-Toolkit-v1.0.2.zip` and `SHA256SUMS-toolkit.txt` from the release.
Compare the ZIP SHA-256 with the value in the release checksum asset.

In PowerShell, run this in the download folder and compare the result:

```powershell
Get-FileHash .\UST-Toolkit-v1.0.2.zip -Algorithm SHA256
Expand-Archive .\UST-Toolkit-v1.0.2.zip -DestinationPath .\UST-download
cd .\UST-download\UST-Toolkit-v1.0.2
Get-FileHash .\lib\matsim-uam-5.0.0.jar -Algorithm SHA256
```

The JAR is 89,251,954 bytes. Its SHA-256 must be:

```text
e0a4e3790b31a7d54bb0abbb52512bd7844184d8b4cc2a74e65e7ad642ea8118
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

The bundle contains the exact tested clean-build executable for MATSim 2024.0
and the locally modified UAM Extension 5.0.0. All manifest-listed files are read back and their
sizes and SHA-256 hashes checked before upload. The release includes the file
manifest. The JAR was built from the supplied source and compared with the
original runtime; all four synthetic original/rebuilt simulations pass. This
does not establish whole-JAR byte reproducibility or validate every historical
simulation. See [build evidence](JAVA-BUILD-VALIDATION.md). See
[runtime provenance](../lib/MATSim/PROVENANCE.json) and
[validation limits](VALIDATION.md).

The original 1.0.0 and 1.0.1 prereleases and their hashes remain available unchanged.
The 34.56 GB MSc archive is separate and is not included in this bundle or Git history.
