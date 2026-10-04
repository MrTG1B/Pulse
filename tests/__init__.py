"""
Pulse Test Suite Package Init.
Ensures src/ is in sys.path for test discovery and execution.
"""

import sys
import os

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
