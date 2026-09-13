# UST Toolkit 1.0.2

Prepared research prerelease with a runtime built from the included Java source.
The repository remains private until the owner changes its visibility.

- Clean Java 21 / Maven build, recorded toolchain and dependency inventory.
- All 163 rebuilt application classes match the original runtime's code.
  Two unreferenced legacy scoring classes in the original JAR are absent.
- Four synthetic simulations pass: original/rebuilt runtime, each with empty
  and explicitly disabled public transport. All 12 travellers arrive in both
  iterations, with matching observed outcomes and no stuck agents.
- Repaired upstream v5.0.0 comparison patch and updated source/runtime provenance.
- Includes the 1.0.1 empty-public-transport fix, compiled dashboard, source,
  documentation, licences, file manifest and SHA-256 checksum.
- Full history and release-content scan runs before asset upload.

Download **UST-Toolkit-v1.0.2.zip** and check **SHA256SUMS-toolkit.txt**.
GitHub's automatic source ZIP does not include the runtime JAR.
See docs/RUNTIME-DOWNLOAD.md and docs/JAVA-BUILD-VALIDATION.md in the bundle.

The 34.56 GB MSc archive remains outside Git and this release. Historical
1.0.0 and 1.0.1 assets remain unchanged. Validation covers synthetic cases,
not reproduction of all historical experiments or arbitrary user scenarios.
