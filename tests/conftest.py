import sys
from pathlib import Path

# The scripts live at the repo root and import _common from there.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
