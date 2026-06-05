#!/usr/bin/env python3
import doctest
import tempfile
import sys
import io
from contextlib import redirect_stdout
from pathlib import Path
import plan

def run_tests():
    print('Testing plan.py via doctest...')

    # 1. Isolated temporary environment
    temp_dir = tempfile.TemporaryDirectory()
    test_file = Path(temp_dir.name) / "plan.txt"

    # 2. Advanced helper to catch stdout AND errors
    def cmd(*args):
        """Runs commands, catches errors, and intercepts stdout cleanly."""
        f = io.StringIO()
        try:
            # Capture any print() statements inside dispatch
            with redirect_stdout(f):
                plan.dispatch(test_file, list(args))
        except plan.ValidationError as e:
            print(f"ValidationError: {e}")
            return
        except plan.UsageError as e:
            print(f"UsageError: {e}")
            return

        # Output the captured text so doctest can verify it
        output = f.getvalue().strip()
        if output:
            print(output)

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
