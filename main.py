#!/usr/bin/env python3
"""GetTracks main entry point."""

import sys
import os

# Add src to path for imports
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

try:
    from gui.main_window import main
except ImportError:
    # Fallback: try direct import
    sys.path.insert(0, project_root)
    from src.gui.main_window import main

if __name__ == "__main__":
    sys.exit(main())
