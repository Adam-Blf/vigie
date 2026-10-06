"""The red teaming scripts live next to their promptfoo config, outside src/, so tests reach
them by putting the repository root on the import path."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
