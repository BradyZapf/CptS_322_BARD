# Contributing

## Branching
- `main` is always deployable/stable.
- Create feature branches off `main`: `feature/<short-description>`, `fix/<short-description>`.
- Rebase or merge `main` into your branch before opening a PR if it has fallen behind.

## Pull Requests
- Keep PRs small and focused on a single change.
- Write a clear description: what changed and why.
- Link related issues/tickets.
- Request at least one review before merging.
- Squash or merge per team convention (agree on one and stick with it).

## Commit Messages
- Use short, imperative subject lines (e.g. "Add login endpoint", not "Added login endpoint").
- Add a body if the change needs more explanation than the subject allows.

## Code Style
- Follow the linting/formatting configuration in `code/backend/` and `code/frontend/`.
- Run tests locally before pushing.
- Document non-obvious decisions with comments; avoid restating what the code already says.

## Issues
- Use the templates in `.github/ISSUE_TEMPLATE/` for bug reports and feature requests.

## Sprint board automation
The sprint board (`.github/workflows/project-board.yml`) moves cards for you:
- A new or reopened issue goes on the board as **To Do**.
- Assigning an issue moves it to **In Progress**.
- Opening a PR (or marking a draft ready, or requesting a review) moves the issue it closes to **Code Review**.
- Closing the issue or merging the PR moves it to **Done** (the board's own built-in workflows).
- **Testing** is still moved by hand.

So the PR description must contain `Closes #<issue number>` (or Fixes/Resolves). The "PR links an
issue" check fails without it; a docs-only PR with no issue can carry the `no-issue` label.

One-time setup: the board belongs to a user account, and the built-in `GITHUB_TOKEN` cannot edit
those, so the repo needs a secret named `PROJECT_TOKEN`. The token can be made by any teammate who can edit the
board (Ryan can); a repo admin (Brady) only pastes it in under Settings > Secrets and variables >
Actions. Use a classic personal access token with the `project` and `repo` scopes: it is known to work for a
user-owned board. A fine-grained token (resource owner BradyZapf, repository `CptS_322_BARD` with
read-only Metadata, Issues and Pull requests, plus the account permission Projects: read and write)
is the narrower option if GitHub allows it for a user-owned board.
Without the secret the workflow prints a notice and passes; the board just does not move.
