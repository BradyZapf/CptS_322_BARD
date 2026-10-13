# Tech stack

To change a choice, open an issue labelled `decision` first.

| Area | Choice | Where it is used |
|---|---|---|
| Language | Python 3.11+ | everything |
| Canvas API | canvasapi, behind `CanvasConnection` | `canvas_connection.py` only |
| Storage + search | SQLite with FTS5 (built into Python) | `search_index.py` |
| Text extraction | pypdf, python-docx (more later) | text copies beside each original |
| Web page | Flask + plain HTML/CSS/JS, no framework | `code/frontend/` (later) |
| AI connector | MCP Python SDK, stdio only, no network port | `ai_connector.py` (later) |
| Unit tests | pytest | `code/backend/tests/` |
| Acceptance tests | behave, running the Gherkin in `features/` | steps to be wired up |
| Browser tests | Selenium | later |
| Fake Canvas | responses + hand-written data in `tests/fakes.py` | all Canvas tests |
| Lint | ruff | CI |
| Editor | VS Code | - |
| Team | Git + GitHub, PRs with one review, GitHub Projects Kanban | - |

## Layout

```
code/backend/src/bard/   the package: one file per class in the class diagram
code/backend/tests/      one test file per story, named after its spec folder
code/frontend/           the web page (later)
features/                Gherkin behaviour specs, tagged @FR-nn @S1-nn
specs/constitution/      this folder: mission, tech stack, roadmap
specs/features/<story>/  requirements.md, plan.md, validation.md for each story
                         (status, owner and points live in the GitHub issue, not here)
docs/design/             the four UML diagrams
docs/                    traceability matrix (requirement -> test), agent notes
scripts/                 repo checks run by CI
```

## UML to Python

Class names stay the same (`CanvasConnection`). Attributes and methods go from camelCase to
snake_case (`getCourseItems` -> `get_course_items`). `-private` attributes get a leading
underscore. Entity classes (Course, CourseItem and its subclasses, Submission, Passage) live in
`models.py`, which is the shared contract.
