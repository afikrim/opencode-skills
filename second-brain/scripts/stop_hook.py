#!/usr/bin/env python3
"""Compatibility alias for the shared automatic filer hook."""
import runpy
from pathlib import Path
if __name__ == "__main__":
    runpy.run_path(str(Path.home()/".codex/hooks/second_brain_stop.py"), run_name="__main__")
