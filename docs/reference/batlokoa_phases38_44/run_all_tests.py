"""Offline tests; PostgreSQL tests skip unless explicitly configured."""
import unittest,sys
suite=unittest.TestSuite()
for location in ('tests','completion_tests','phase43_tests'):
    suite.addTests(unittest.defaultTestLoader.discover(location,top_level_dir='.'))
result=unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
