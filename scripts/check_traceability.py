"""Fail if a feature file or a test file is not mentioned in docs/TraceabilityMatrix.md.

Run from the repo root:  python scripts/check_traceability.py
CI runs it on every pull request, so the matrix cannot quietly fall behind the code.
"""

import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
matrix = (root / "docs" / "TraceabilityMatrix.md").read_text(encoding="utf-8")

missing = []
for f in sorted((root / "features").glob("*.feature")):
    if f.stem not in matrix:
        missing.append(f"features/{f.name}")
for t in sorted((root / "code" / "backend" / "tests").glob("test_*.py")):
    if t.stem not in matrix:
        missing.append(f"code/backend/tests/{t.name}")

if missing:
    print("Not in docs/TraceabilityMatrix.md (add a row for each):")
    for m in missing:
        print("  " + m)
    sys.exit(1)
print("Traceability matrix covers every feature file and test file.")
