# S2-C File work: requirements

**Covers:** FR-03, FR-04, FR-06

**User story.** As a student, I want to search inside my downloaded PDFs and Word files and to keep my own handed-in work, so that my archive is complete.

**Gherkin:** `features/files_linked_inside_a_course.feature`, `features/searching_in_plain_language.feature`, `features/coverage_report.feature`

Items: S2-10 to S2-12, see `docs/ProjectManagement/SprintBacklog.md`. This part uses the shared format from S2-A (a status and a reason on every file).

## S2-10 Text from PDF and Word files

### Acceptance criteria

- A PDF with text and a Word (.docx) file each get a .md copy in the same folder as the original
- The .md copy is named after the whole original name plus `.md`, so `report.pdf` and `report.docx` cannot collide
- The original is kept
- The text is stored on the `CourseFile` and added to the search index, so a phrase that exists only inside the file is found by search
- `CourseFile.extract_text()` no longer raises `NotImplementedError`, and uses `pypdf` and `python-docx`
- A second sync does not rewrite the .md of a file that has not changed (NFR-03)
- Files that are not PDF or Word are left alone and get no .md

## S2-11 Mark scanned and locked PDFs as unreadable

### Acceptance criteria

- A PDF with no text, such as a scan, gets the status unreadable and a reason such as "no text found, probably a scan"
- A PDF locked with a password BARD does not have gets the status unreadable and a reason that says it is locked; a PDF that opens with an empty password is read normally
- A damaged file gets the status unreadable and does not stop the sync
- For every unreadable file the original is kept and no .md is written
- Unreadable files are listed in the report with their reason (S2-A)

## S2-12 Download the user's own submission files

### Acceptance criteria

- Canvas is asked through `CanvasConnection`, the only class that talks to Canvas
- The files attached to the user's own submission are saved in the course folder, named so it is clear which assignment they belong to
- Only the user's own submission is requested, never another student's, and a test fails if any other request is made
- An assignment with no submission saves nothing and is not an error
- A file that cannot be saved gets a status and a reason
- The test fake (`tests/fakes.py`) covers a submission with a file and one without
