"""Conftest - ensure polymarket modules are importable."""
import sys
from pathlib import Path

# Ensure we import from the polymarket directory, not workspace root
polymarket_dir = Path(__file__).parent.parent

# Remove any stale/old copies of polymarket_weather_scanner_final from sys.path
# that would shadow the local one
stale_entry = str(Path("C:/Users/Administrator/.openclaw/workspace/polymarket_weather_scanner_final.py"))
sys.path = [p for p in sys.path if p != stale_entry and "workspace\\polymarket_weather_scanner_final" not in p]

# Prepend polymarket_dir to ensure local module is found first
if str(polymarket_dir) not in sys.path:
    sys.path.insert(0, str(polymarket_dir))

# Also clear any cached imports of this module
for key in list(sys.modules.keys()):
    if "polymarket_weather_scanner_final" in key:
        del sys.modules[key]
