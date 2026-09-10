# User-supplied network data

Place the new scenario's default network here:

```text
data/base_network.xml
```

Alternatively, set `BASE_NETWORK_PATH` in `src/config.py` or the
`UST_BASE_NETWORK_PATH` environment variable.

The pipeline's preparation and topology stages expect an uncompressed MATSim
network XML. Coordinates in `src/config.py` must use the same projected CRS and
units as this network. Module 5 also needs that CRS in `MODULE5_CRS`.

No network is included in the source toolkit. The folder is ignored by Git to
reduce the risk of publishing a large or separately licensed dataset. Before
sharing a network, verify provenance, redistribution rights, required
attribution, and privacy or security constraints.
