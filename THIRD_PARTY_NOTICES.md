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
terms. A clean build of the supplied modified source and comparison with the
original runtime are recorded in docs/JAVA-BUILD-VALIDATION.md. The 1.0.2 JAR
comes from that clean build; it is a modified UST runtime.

The 94 embedded Maven POMs and eight licence/notice paths are inventoried in
docs/evidence/bundled-dependencies.json; resolved dependency coordinates are in
docs/evidence/dependency-tree.txt. These records and preserved embedded notices
supplement the supplied source and Maven build declaration. Dependency licences
remain applicable; the inventory is not a blanket legal certification.

## Python and frontend packages

Python dependencies are declared in requirements.txt and src/module5/requirements.txt.
Frontend dependencies and their resolved versions are declared in package.json
and pnpm-lock.yaml under src/module5/frontend. Frontend licence inventory and
available installed licence texts are in third_party/frontend-licenses/.
These files are an inventory, not a replacement for the original licence terms.

## Preserved upstream test fixtures

The eight Corsica files under lib/MATSim/src/test/resources/corsica match
MATSim-UAM v5.0.0 exactly. They retain upstream attribution and terms. See
docs/PUBLIC-CONTENT-REVIEW.md and its blob-identity evidence.

## Study inputs and outputs

The MSc archive is separate from the fresh toolkit. A toolkit code licence
does not establish redistribution rights for the base network, other datasets,
or third-party material in research documents. Those terms remain to be confirmed.

## Original UST code

Copyright (C) 2026 Chirag Srinivas. Original UST code is licensed under
GPL-3.0-only at the owner's direction. See LICENSE and COPYRIGHT.md.
Third-party terms and attribution are retained.
