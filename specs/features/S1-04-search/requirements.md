# S1-04 Search my coursework: requirements

**Covers:** FR-06, NFR-04

**User story.** As a student, I want to search my coursework in plain language and see the passage that answers me so that I do not have to remember which file it was in.

**Gherkin:** `features/searching_in_plain_language.feature`.

## Acceptance criteria

- `add_item()` indexes an item's `to_text()`; adding it again replaces it
- `search()` returns passages, best first, each naming its course and title
- A search with no match returns an empty list, never unrelated passages
- A search over the test archive takes under one second
- `python -m bard search "late policy"` works after a sync
