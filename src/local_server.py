"""Standalone local-server launcher for the UST Module 5 dashboard.

The analytics implementation remains in :mod:`module5`; this file provides a
separate, obvious server entry point for users who only want to inspect an
existing MATSim run.
"""

from __future__ import annotations

import sys

from module5 import server_main as module5_server_main


def main(argv: list[str] | None = None) -> int:
    """Start Module 5's local FastAPI server."""
    arguments = sys.argv[1:] if argv is None else argv
    return module5_server_main(
        arguments,
        prog="python src/local_server.py",
    )


if __name__ == "__main__":
    raise SystemExit(main())
