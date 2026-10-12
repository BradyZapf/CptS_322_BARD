# S1-05 Erase everything: requirements

**Covers:** FR-10

**User story.** As a student who has finished with BARD, I want to erase everything it has stored so that nothing of mine is left on the machine.

**Gherkin:** `features/erasing_everything.feature`.

## Acceptance criteria

- The archive folder and the saved token are both removed
- If anything cannot be removed, return False and name it; never report a partial erase as complete
- Tell the user how to revoke the token in Canvas (Account > Settings > Approved Integrations)
- `python -m bard erase` asks for confirmation first
