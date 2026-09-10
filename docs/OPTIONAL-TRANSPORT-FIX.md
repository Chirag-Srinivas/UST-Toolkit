# Optional public transport correction — 1.0.1

Version 1.0.1 fixes the UAM/car-only failure discovered in the original
1.0.0 prepared release. Empty `trains` and `buses` lists, or
`TRANSPORT_SUPPLY = {"enabled": False}`, now retain the UAM fleet and network
without requiring any scheduled public transport.

Module 3 writes an empty schedule and zero transit vehicles. The MATSim v2
vehicle schema requires at least one vehicle type, so the file contains an
unused `unused_no_pt` type. It introduces no vehicles, departures or services.
The supplied Java runtime is unchanged.

Demand defaults to UAM/car alternatives when no scheduled service exists.
An explicit `pt_plan_enabled=True` or `initial_ground_plan="pt"` without
services is rejected before simulation. `pipeline.py --check` now validates
transport configuration too. Configured bus/train demand keeps its PT default.

## Validation on 10 September 2026

- All 15 Python tests pass, including six new regression tests for optional
  transport, demand alternatives, preflight checks and configured bus behavior.
- Python source and test compilation pass.
- The actual Java 21 / MATSim runtime completes iterations 0 and 1 with both
  empty service lists and explicitly disabled PT. Tests use the isolated
  Python 3.12.14 environment installed for the original fresh-install check.
- Each run has two synthetic vertiports, four UAM vehicles and 12 passengers.
  All 12 passengers reach their destinations in both iterations; no stuck
  events occur. UAM pickup/drop-off counts match: 8/8 in iteration 0 and 4/4
  in iteration 1. Final analytics report four UAM and eight car outcomes,
  zero PT outcomes and zero unobserved travellers.
- No generated PT passenger legs, scheduled services or transit vehicles.
  All five analytics Parquet tables contain data; score history is finite.
- Machine-readable evidence: [empty services](validation/2026-09-10-no-pt-fix/empty-services-results.json)
  and [disabled PT](validation/2026-09-10-no-pt-fix/disabled-results.json).

These synthetic checks establish the correction, not convergence or scientific
validity of a study. The runtime still emits its existing topology/deprecation
warnings. A clean source-to-binary rebuild and reproduction of all historical
MSc simulations remain unverified. See [validation limits](VALIDATION.md).

The original 1.0.0 release, runtime JAR hash and large MSc archive are preserved.
The corrected bundle is distributed separately as `v1.0.1-prepared`; the MSc
archive and executable binaries remain outside Git history.
