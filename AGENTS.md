# AGENTS.md: rules for every coding agent (and every person) working on BARD

Four people work on this repo, each possibly with their own AI coding agent (Claude Code,
Codex, Copilot, Cursor, ...). This file is how all of those agents stay on the same track. It
is the project's constitution in short form. Read the full one in `specs/constitution/`.

## 1. Read before you write

1. `specs/constitution/mission.md`: what BARD is, and the 8 rules no change may break.
2. `specs/constitution/tech-stack.md`: the chosen tools and the folder layout.
3. Your story's GitHub issue (`gh issue view <number>`) for who owns it and its status, then its
   spec: `specs/features/<story>/requirements.md`, `plan.md`, `validation.md`. The issue links the spec.
4. The matching Gherkin in `features/` and the test file named in `validation.md`.
5. The design: `docs/design/` (class, sequence, collaboration, use case diagrams).

The specs are the source of truth, not the chat. If the chat and a spec disagree, the spec
wins until a human changes it.

## 2. Plan, implement, verify

- **Plan.** Before editing anything, say back what the story asks, which files you will
  change, and which test proves it is done. Wait for the human to confirm.
- **Implement** only inside the files listed in the story's `plan.md`.
- **Verify.** Run `pytest` and `ruff check .`. Paste the result. A story is done when its tests
  pass with no "not built yet" skips (a skip that says it does not apply on your OS, e.g. Windows, is fine; CI runs all three OSes), not when the code "looks right". Never say done without running them.

## 3. Stay in your lane

- One story = one branch = one pull request. Branch names: `feature/S1-03-upcoming-work`,
  `fix/<short-description>` (CONTRIBUTING.md).
- Edit only the files your story's `plan.md` lists.
- **`code/backend/src/bard/models.py` is the shared contract.** Do not rename or remove
  anything in it inside a feature branch. If your story needs a change there, stop and tell
  the human. It goes in its own small pull request that the whole team approves first.
- **Refining your own story's spec is the engineer's call.** You may edit your story's
  `requirements.md` and `plan.md` in the same pull request when the change is an
  implementation detail (an extra safety check, a clearer message, a reordered step). The
  reviewer sees it in the diff. Ask the team first only if the change alters the UML in
  `docs/design/`, `models.py`, a `features/*.feature` file, or what the story delivers to the
  user (new scope, a new requirement ID, another story's files).
- Do not weaken, skip or delete a test to make it pass. If a test looks wrong, say so.
- Do not touch `features/*.feature` wording: it is the behaviour spec. Change the requirement
  first, as a team.

## 4. Hard rules (from mission.md)

- GET requests to Canvas only. Never POST, PUT or DELETE.
- Nothing leaves the user's computer except calls to their own Canvas.
- Never print, log or commit a token. Never commit a real Canvas response or real coursework.
  Test data is hand-written in `code/backend/tests/fakes.py`.
- No AI generation inside BARD. Search returns real passages.
- Python 3.11+, standard library first. Ask before adding a dependency.

## 5. Writing code here

- UML names map to Python: class names unchanged, methods and attributes in snake_case
  (`getCourseItems` -> `get_course_items`).
- Prefer plain, explicit code over clever Python. Type hints on every function.
- `sync.py` mirrors the sequence diagram. If you change its order, update the diagram.

## 6. Pull requests

Fill in `.github/pull_request_template.md`, including the AI-use section. A teammate reviews
before merge. CI runs `pytest` and `ruff` on every pull request.

## 7. Where things live (so nothing is updated in two places)

| Fact | Lives in |
|---|---|
| What a story means, which files it touches, acceptance criteria | `specs/features/<story>/` (changes by pull request) |
| Who owns it, status, priority, points | the GitHub issue and the board, never a file |
| Which requirement is tested where | `docs/TraceabilityMatrix.md` (CI checks it is complete) |
| What BARD is and the rules | `specs/constitution/` |

An agent will say it finished whether or not it works. The proof is the test output and the
pull request checklist, never the agent's summary. When an agent stops partway, it can leave
`specs/features/<story>/notes.md` (what is done, what is next, what surprised it) for the next
session.

## 8. Personal notes

Your own preferences go in `CLAUDE.local.md` or `AGENTS.local.md`. Both are gitignored, so
they bind only you. Anything the whole team needs goes here instead.
