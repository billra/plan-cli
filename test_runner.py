#!/usr/bin/env python3
import doctest
import tempfile
import sys
from pathlib import Path
import plan

def run_tests():
    print('Testing plan.py via doctest...')

    # 1. Isolated temporary environment
    temp_dir = tempfile.TemporaryDirectory()
    test_file = Path(temp_dir.name) / "plan.txt"

    # 2. Simplified helper to catch errors (doctest naturally intercepts stdout)
    def cmd(*args):
        """Runs commands and catches errors for doctest to see."""
        try:
            plan.dispatch(test_file, list(args))
        except (plan.ValidationError, plan.UsageError) as e:
            print(f"{type(e).__name__}: {e}")

    # 3. Inject our tools
    extraglobs = {
        'cmd': cmd,
        'test_file': test_file
    }

    # 4. Execute the text file
    results = doctest.testfile("test_plan.txt", extraglobs=extraglobs)

    # 5. Clean up
    temp_dir.cleanup()

    if results.failed == 0:
        print("All tests passed! ✨")

    sys.exit(results.failed)

if __name__ == "__main__":
    run_tests()
