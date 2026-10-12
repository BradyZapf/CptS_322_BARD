# S1-00 Project skeleton and the sync pipeline: requirements

**Covers:** FR-02, FR-04 (part), NFR-03, NFR-07

**User story.** As a developer on the team, I want a project skeleton built from our UML so that each of us can build one class without waiting on the others.

## Acceptance criteria

- The package has one file per class in the class diagram, with the UML methods
- `SyncCoursework.sync()` follows the sequence diagram step for step
- `SyncReport` groups missed files by reason
- `pytest` runs green on a fresh clone: built parts pass, unbuilt stories show as skipped
- AGENTS.md, the constitution and one spec per story exist
