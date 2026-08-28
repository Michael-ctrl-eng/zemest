"""Fixtures shared across scraper tests."""
from __future__ import annotations

import os
import sys

# Import root conftest so shared fixtures are available.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
