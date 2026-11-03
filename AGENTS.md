# AGENTS.md: rules for every coding agent (and every person) working on BARD

Four people work on this repo, each possibly with their own AI coding agent (Claude Code,
Codex, Copilot, Cursor, ...). This file keeps them on the same track; the full constitution is
in `specs/constitution/`.

## 1. Read before you write

1. `specs/constitution/mission.md`: what BARD is, and the 8 rules no change may break.
2. `specs/constitution/tech-stack.md`: the chosen tools and the folder layout.
3. Your story's GitHub issue (`gh issue view <number>`) for who owns it and its status, then its
   spec: `specs/features/<story>/requirements.md`, `plan.md`, `validation.md`. The issue links the spec.
   Read the "done when" checks in `validation.md` first: they say what to build and how it is proven.
4. The matching Gherkin in `features/` and the test file named in `validation.md`.
5. The design: `docs/design/` (class, sequence, collaboration, use case diagrams).

The specs are the source of truth, not the chat. If the chat and a spec disagree, the spec
wins until a human changes it.

## 2. Plan, implement, verify

- **Plan.** Before editing anything, say back what the story asks, which files you will
  change, and which test proves it is done. Then go: stop and wait only for what section 3
  says to ask the team. A small choice inside your own story is yours; make it, note it in the
  pull request, and keep going.
- **Checks first.** Write or confirm the test (and any fake case it needs) for each "done when"
  check before the code, so you can build the whole story and verify it in one pass.
- **Implement** only inside the files listed in the story's `plan.md`. Fix the cause, not the
  symptom: if a test fails, find out why before changing code or test.
- **Verify.** Run the full `pytest`, `ruff check .` and `python scripts/check_traceability.py`.
  Paste the result. A story is done when all pass with no "not built yet" skips (a skip that
  says it does not apply on your OS is fine; CI runs all three OSes), not when the code "looks
  right". Never say done without running them.
- **Tests must cover the story, not just pass.** Passing tests only count if they would fail
  when the feature breaks.
  - Every bullet in the story's `requirements.md` has a test. Tick them off one by one in the
    pull request.
  - Test the failure paths too (bad input, nothing found), checking the result and the message,
    not only that it did not crash.
  - Test every place your code is wired into someone else's (for example the call you add in
    `sync.py`): delete the call and a test must fail. "I tried it by hand" is not a test.
  - If the story needs a Canvas response the fake in `tests/fakes.py` cannot give yet (a
    blocked tab, a locked file, a quota header), add that case to the fake, hand-written.
  - Code that touches the token or deletes files needs a test for what happens when it fails.

## 3. Stay in your lane

- One story = one branch = one pull request. Branch names: `feature/S1-03-upcoming-work`,
  `fix/<short-description>` (CONTRIBUTING.md). Keep each PR small; split a big story into a
  stack.
- **Stacking.** If your work needs another open PR, branch from that PR's branch and open yours
  against it (title `S2-03: ...`, description starting "Based on #<n>"). When the one below
  merges, retarget yours to `main`. Fix a gap in the earliest PR that owns it, then merge up.
- Edit only the files your story's `plan.md` lists.
- **`code/backend/src/bard/models.py` is the shared contract.** Adding to it is fine inside
  your story's pull request when the new field or class has a default, so nobody's code
  breaks: say so in one line in the PR. Renaming, removing or changing the type of anything
  there breaks other people's code: stop and tell the human. That goes in its own small pull
  request that the whole team approves first.
- **Hand-offs.** Each story's `requirements.md` has a short "Depends on / provides" list:
  what it reads from other stories (fields, folders, files, statuses) and what it hands to
  them. If you change something another story reads, update that story's spec in the same
  pull request and tag its owner.
- **Decide alone:** implementation details of your own story (an extra safety check, a clearer
  message, a reordered step, a tuning number). You may edit your story's `requirements.md` and
  `plan.md` in the same pull request; the reviewer sees it in the diff, and you list it in the
  PR. **Ask the team first** if it alters the UML in `docs/design/`, renames or removes
  anything in `models.py`, changes a `features/*.feature` file, or changes what the story
  delivers (new scope, a new requirement ID, another story's files).
- Do not weaken, skip or delete a test to make it pass. If a test looks wrong, say so. Do not
  touch `features/*.feature` wording: change the requirement first, as a team.

## 4. Hard rules (from mission.md)

- GET requests to Canvas only. Never POST, PUT or DELETE.
- Nothing leaves the user's computer except calls to their own Canvas.
- Never print, log or commit a token. Never commit a real Canvas response or real coursework.
  Test data is hand-written in `code/backend/tests/fakes.py`.
- A run against real Canvas is read-only, uses a throwaway home folder you delete afterwards,
  and its output stays out of the repo. Report counts and findings, not content.
- No AI generation inside BARD. Search returns real passages.
- Python 3.11+, standard library first. Ask before adding a dependency.

## 5. Writing code here

- UML names map to Python: class names unchanged, methods and attributes in snake_case
  (`getCourseItems` -> `get_course_items`).
- Prefer plain, explicit code over clever Python. Type hints on every function.
- `sync.py` mirrors the sequence diagram. If you change its order, update the diagram.

## 6. Pull requests

Fill in `.github/pull_request_template.md`, including the AI-use section. Commit messages: a
short imperative subject, then a body saying why. The PR description says what changed and why,
which "done when" checks pass (with the test counts), what you decided alone, and what you want
the reviewer to decide. A teammate reviews before merge. CI runs `pytest`, `ruff` and the
traceability check on every pull request.

## 7. Where things live (so nothing is updated in two places)

| Fact | Lives in |
|---|---|
| What a story means, which files it touches, acceptance criteria | `specs/features/<story>/` (changes by pull request) |
| Who owns it, status, priority, points | the GitHub issue and the board, never a file |
| Which requirement is tested where | `docs/TraceabilityMatrix.md` (CI checks it is complete) |
| What BARD is and the rules | `specs/constitution/` |
| Design, test plan and reports | `docs/design/`, `docs/Reports/`: change them in the PR that changes the behaviour |

An agent will say it finished whether or not it works. The proof is the test output and the
PR checklist, never the summary. An agent that stops partway can leave
`specs/features/<story>/notes.md` (done, next, surprises) for the next session.

## 8. Personal notes

Your own preferences go in `CLAUDE.local.md` or `AGENTS.local.md`. Both are gitignored, so
they bind only you. Anything the whole team needs goes here instead.
