# Third-party components

UST builds on work by the MATSim and MATSim-UAM communities. Original authors
and contributors retain their copyright and licence terms.

## Modified MATSim-UAM

- Upstream: https://github.com/BauhausLuftfahrt/MATSim-UAM
- Original project credits include Raoul Rothfeld and Milos Balac, with support
  from Aitan Militão and Sebastian Hörl; see the preserved upstream README.
- Licence: GPL-3.0; text in lib/MATSim/LICENSE.
- Local modifications and comparison basis: lib/MATSim/MODIFICATIONS.md.
- Java source and build declaration: lib/MATSim/src and lib/MATSim/pom.xml.
- The fresh toolkit release ZIP includes the modified executable. Its checksum
  is recorded in lib/MATSim/PROVENANCE.json.

The executable also bundles dependencies with their own applicable licence
terms. A current clean rebuild/corresponding-source audit has not been completed.
Do not describe the binary as an unmodified upstream release.

## Python and frontend packages

Python dependencies are declared in requirements.txt and src/module5/requirements.txt.
Frontend dependencies and their resolved versions are declared in package.json
and pnpm-lock.yaml under src/module5/frontend. Frontend licence inventory and
available installed licence texts are in third_party/frontend-licenses/.
These files are an inventory, not a replacement for the original licence terms.

## Study inputs and outputs

The MSc archive is separate from the fresh toolkit. A toolkit code licence
does not establish redistribution rights for the base network, other datasets,
or third-party material in research documents. Those terms remain to be confirmed.

## Original UST code

Copyright (C) 2026 Chirag Srinivas. Original UST code is licensed under
GPL-3.0-only at the owner's direction. See LICENSE and COPYRIGHT.md.
Third-party terms and attribution are retained.
