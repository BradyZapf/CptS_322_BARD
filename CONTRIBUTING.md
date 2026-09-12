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
