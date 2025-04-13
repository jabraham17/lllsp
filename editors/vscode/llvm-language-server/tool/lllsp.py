import sys
import os

extension_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bundled = os.path.join(extension_dir, "bundled", "libs")
sys.path.insert(0, bundled)

from lllsp.cli import run
run()
