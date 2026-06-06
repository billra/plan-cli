#!/usr/bin/env python3
import doctest
import tempfile
import sys
from pathlib import Path
import plan

def run_tests():
    print('Testing plan.py via doctest...')

    # 1. Isolated temporary environment via Context Manager
    with tempfile.TemporaryDirectory() as temp_dir:
        plan_file = Path(temp_dir) / "plan.txt"

        # 2. Simplified helper to catch errors
        def cmd(*args):
            """Runs commands and catches errors for doctest to see."""
            try:
                plan.dispatch(plan_file, list(args))
            except (plan.ValidationError, plan.UsageError) as e:
                print(f"{type(e).__name__}: {e}")

        # 3. Inject our tools
        extraglobs = {
            'cmd': cmd,
            'plan_file': plan_file
        }

        # 4. Execute the text file
        results = doctest.testfile("test_plan.txt", extraglobs=extraglobs)

    if results.failed == 0:
        print(f"✨ Success! All {results.attempted} tests passed.")
    else:
        print(f"❌ Failed: {results.failed} out of {results.attempted} tests.")

    sys.exit(results.failed)

if __name__ == "__main__":
    run_tests()
