# Public-content review

Reviewed 13 September 2026. Repository visibility remains private.

The [initial audit](https://github.com/Chirag-Srinivas/UST-Toolkit/actions/runs/34591945013)
scanned 410 unique history blobs and all 506 files in the 1.0.1 release ZIP.
It found no matches for the scanned credential patterns and no forbidden
archive/key paths in Git history. The ZIP contained the expected runtime JAR
and no nested research archives. Evidence is preserved in
[evidence/public-content-review-1.0.1.json](evidence/public-content-review-1.0.1.json).

The 1.0.2 packaging workflow repeats the scan against its complete Git history
and candidate ZIP before upload. Its release asset `public-content-review.json`
records the final counts and ZIP hash. The scan covers common private-key,
GitHub-token, AWS access-ID, Slack-token and OpenAI-key patterns; it does not
guarantee detection of every credential format.

## Data scope

The toolkit excludes the owner's study base network, generated scenarios,
population, results and 34.56 GB MSc archive. Its clean configuration needs
user-supplied inputs.

Eight files under `lib/MATSim/src/test/resources/corsica/` are preserved upstream
test fixtures. Each Git blob matches the official MATSim-UAM v5.0.0 commit
`d11241567d56c262da8cdd5752828556f9080d68` exactly. See
[evidence/upstream-test-data.json](evidence/upstream-test-data.json).
These are upstream fixtures, not the owner's MSc inputs. Upstream credit and
licence materials remain included; blob identity establishes origin, not
additional rights to unrelated study datasets.

## Notices and dependencies

The runtime contains 94 embedded Maven POMs and eight licence/notice paths.
Forty-four POMs declare licences directly; the remaining 50 omit declarations
or inherit them. An omitted child-POM declaration is not itself evidence of an
unlicensed dependency. Original and rebuilt inventories agree.

[evidence/bundled-dependencies.json](evidence/bundled-dependencies.json) records
the exact runtime hashes, POM paths, declared terms and notice paths.
[evidence/dependency-tree.txt](evidence/dependency-tree.txt) records resolved
dependency coordinates; build repositories are declared in the supplied POM.
The Java source, build file, upstream GPL text, embedded dependency notices and
frontend licence inventory are retained. Dependencies keep their own terms.
This inventory is not a blanket legal certification of every dependency or
user-provided dataset.

The historical releases remain preserved. Future changes to source, runtime
dependencies, inputs or assets should repeat the relevant checks.
