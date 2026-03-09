#!/usr/bin/env python3
"""GetTracks main entry point."""

import sys
import os

# Ensure project root and src directory are on the path for imports
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')

# project_root allows absolute imports of the 'src' package
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# src_path allows treating gui as top-level module
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import main entrypoint from gui package
from gui.main_window import main

if __name__ == "__main__":
    sys.exit(main())
