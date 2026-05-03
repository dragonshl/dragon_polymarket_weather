"""Conftest - ensure polymarket modules are importable."""
import sys
from pathlib import Path

# Ensure we import from the polymarket directory, not workspace root
polymarket_dir = Path(__file__).parent.parent
if str(polymarket_dir) not in sys.path:
    sys.path.insert(0, str(polymarket_dir))
