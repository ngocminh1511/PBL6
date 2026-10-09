"""Backward-compatible entrypoint for the v4 competency-question suite.

The former test queried pre-v4 predicate names. It now delegates to the
schema-v4 suite so the historical command remains usable without maintaining
two incompatible vocabularies.
"""
from __future__ import annotations

import sys

from test_cq_v4 import main


if __name__ == "__main__":
    sys.exit(main())
