# S2-D Errors, erase, guide file and test fake: validation

Done means all of these are true. The pull request template has the checklist to tick.

- `pytest code/backend/tests/test_s1_01_connect.py`, `test_s1_05_erase.py`, `test_s2_d_guide_file.py` and `test_s2_d_fakes.py` pass
- `pytest` (everything) still passes
- `ruff check .` is clean
- `docs/TraceabilityMatrix.md` has a row for each new test file, so the traceability check passes
- Every acceptance criterion in requirements.md is ticked
- Each Canvas error gives one clear message and no traceback
- Erase removes the new files too
- The guide file exists after a sync and holds no token and no coursework text
- Tried by hand with `BARD_HOME` set to a throwaway folder, never a real one: connect with a wrong token and with an address that does not exist, run a sync, then erase
- Pull request reviewed by one teammate and linked to its issue; the one for S2-14 says `Refs #14`, not `Closes #14`, because it only covers part of that issue
- AI use, if any, written in the pull request
