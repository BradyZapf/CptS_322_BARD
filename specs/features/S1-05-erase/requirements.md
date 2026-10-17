# S1-05 Erase everything: requirements

**Covers:** FR-10

**User story.** As a student who has finished with BARD, I want to erase everything it has stored so that nothing of mine is left on the machine.

**Gherkin:** `features/erasing_everything.feature`.

## Acceptance criteria

- The archive folder and the saved token are both removed
- If anything cannot be removed, return False and name it; never report a partial erase as complete
- Tell the user how to revoke the token in Canvas (Account > Settings > Approved Integrations)
- `python -m bard erase` asks for confirmation first
- Before asking, it shows exactly what will be removed: the archive folder's path and what is in it,
  and the token file's path
- It refuses, removing nothing, if the archive folder is the user's home folder, contains the home
  folder, or is the top of a drive; it names the folder and says why (a wrong `BARD_HOME` must never
  delete unrelated files)
