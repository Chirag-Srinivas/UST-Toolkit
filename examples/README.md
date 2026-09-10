# Small examples without the MSc dataset

The fresh toolkit starts with empty scenario settings. To try small, synthetic
inputs without downloading the research archive, the following executable tests
also serve as examples:

- `tests/test_background_traffic.py` creates a four-node road network and
  generates a small synthetic population.
- `tests/test_fato_topology.py` attaches a synthetic vertiport and checks that
  arrivals/departures use the shared FATO capacity constraint.
- `tests/test_extractor.py` creates sample events, extracts analytics and checks
  the results. It does not run a complete MATSim simulation.

After installing the toolkit's Python requirements, run from the repository:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

On macOS/Linux use `PYTHONPATH=src python -m unittest discover -s tests -v`.
The examples write to temporary directories. For your own full simulation,
follow `experiment_inputs/README.md`, supply a network and configure `src/config.py`.
