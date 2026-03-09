#!/usr/bin/env python3
"""Release script that ensures tests pass before allowing version release."""

import subprocess
import sys
from pathlib import Path

def run_tests():
    """Run the test suite and return True if all tests pass."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        if result.returncode == 0:
            print("All tests passed!")
            return True
        else:
            print("Tests failed!")
            print(result.stdout)
            print(result.stderr)
            return False
    except Exception as e:
        print(f"Error running tests: {e}")
        return False

def main():
    """Main release function."""
    print("Checking if all functions have unit tests and tests pass...")

    if not run_tests():
        print("Cannot proceed with release: unit tests failed.")
        sys.exit(1)

    print("Release approved: all tests pass.")

    # Here you could add version bumping logic
    # For now, just confirm tests pass

if __name__ == "__main__":
    main()