"""
Pulse — Application Launcher.
Entry point delegating to src.app.main().
"""

import sys
import os

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from src.app import main

if __name__ == "__main__":
    main()
