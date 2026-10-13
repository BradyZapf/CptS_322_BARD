# Getting started on BARD

BARD downloads your Canvas coursework to your own computer so you can search it and point
your own AI tool at it. It only reads from Canvas, and nothing leaves your machine.

The code is a skeleton built from our UML diagrams. Every class in the class diagram has a
file, and every story has a spec and a test file waiting for it. A method that is not built yet
raises `NotImplementedError`, and its tests show as **skipped** until someone builds it.

## 1. Set up (10 minutes)

You need Python 3.11 or newer and Git.

```
git clone https://github.com/BradyZapf/CptS_322_BARD
cd CptS_322_BARD
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -e ".[dev]"
pytest -rs
```

You should see a few tests passed and the rest skipped, each with the reason "not built yet".
That is the starting point: your job is to turn skips into passes. (On Windows a few extra tests
skip because they only apply to Linux and macOS; CI checks those.)

Optional but recommended: install the GitHub CLI (`gh`) and run `gh auth login`. Then you and
your coding agent can read the issues from the terminal.

## 2. Pick your story

The work is tracked in **GitHub Issues**, and the Kanban board is **GitHub Projects**. They are
the only place that says who owns a story and what state it is in. No file in the repo does.

- Web: the repo's **Issues** tab, or the **Projects** tab for the board.
- Terminal: `gh issue list`, and `gh issue view <number>` for one story.

Assign yourself the issue you are taking. The issue links the story's spec folder.

## 3. Read the spec, then build

Everything about what to build is in `specs/features/<story>/` (the story IDs are in the issue
titles, like `S1-03`):

- `requirements.md`: the user story and acceptance criteria
- `plan.md`: which files the story touches and the steps
- `validation.md`: what "done" means

Then:

1. `git switch -c feature/s1-03-upcoming-work` (a branch per story, named after its spec folder).
2. Replace the `raise NotImplementedError(...)` lines in your methods with real code.
3. `pytest -k s1_03 -v` until your story's tests pass instead of skipping. Run plain `pytest`
   and `ruff check .` before you push.
4. Push, open a pull request, fill in the template, and write `Closes #<issue number>` in it.
   One teammate reviews before it merges. The board moves the card by itself.

If you change `models.py` (the shared types), do it in its own small pull request that the
whole team approves, because every other module imports from it.

If you add a `.feature` file or a test file, add a row for it in `docs/TraceabilityMatrix.md`.
CI fails until you do.

## 4. Using an AI coding agent

Start it with:

> Read AGENTS.md, then read the GitHub issue for story S1-03 and its spec folder in
> specs/features/. Tell me your plan before changing anything.

`CLAUDE.md` points Claude Code at `AGENTS.md`; other agents read `AGENTS.md` directly. Check the
agent's plan against `plan.md` before it starts writing, and note any AI use in the pull request.
The proof that something works is the `pytest` output, not the agent saying it is done.
Personal preferences go in `CLAUDE.local.md` or `AGENTS.local.md`, which are gitignored.

## 5. Find your way around

| You want | Look at |
|---|---|
| what BARD is, and the rules no change may break | `specs/constitution/mission.md` |
| the chosen tools and the folder layout | `specs/constitution/tech-stack.md` |
| the design | `docs/design/` (use case, class, collaboration, sequence diagrams) |
| a story's details | `specs/features/<story>/` |
| who owns a story, and its status | the GitHub issue and the board |
| the code | `code/backend/src/bard/` (one file per class) |
| a story's tests | `code/backend/tests/` |
| the expected behaviour in Gherkin | `features/` |
| which requirement is tested where | `docs/TraceabilityMatrix.md` |
| rules for AI coding agents | `AGENTS.md` |
