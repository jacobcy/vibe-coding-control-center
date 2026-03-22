#!/usr/bin/env python3
from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parent.parent
runpy.run_path(str(ROOT / "scripts" / "tools" / "serena_gate.py"), run_name="__main__")
