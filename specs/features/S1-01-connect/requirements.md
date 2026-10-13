# S1-01 Connect a Canvas account: requirements

**Covers:** FR-01, NFR-06

**User story.** As a student setting up BARD, I want to connect my Canvas account once so that I do not have to configure it again.

**Gherkin:** `features/connecting_a_canvas_account.feature`.

## Acceptance criteria

- A token Canvas accepts is saved with the Canvas address
- A token Canvas rejects (401) is not saved, and the user is told it was rejected
- The saved file can be read by the user's own account only (chmod 600 on Linux/macOS)
- The token is never printed or logged
- `python -m bard connect` works end to end
