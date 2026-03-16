#!/usr/bin/env python3
"""GetTracks main entry point."""

import sys
import os

# Ensure project root is on the path so 'src.*' imports resolve correctly
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.gui.main_window import main

if __name__ == "__main__":
    sys.exit(main())
