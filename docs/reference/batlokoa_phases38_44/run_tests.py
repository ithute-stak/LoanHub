"""Run isolated new offline tests from any current working directory."""
from pathlib import Path
import sys
import unittest
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))
suite = unittest.defaultTestLoader.discover(start_dir=str(root / 'tests'), pattern='test_*.py', top_level_dir=str(root))
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
