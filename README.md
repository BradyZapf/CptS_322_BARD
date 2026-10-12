# CptS_322_BARD

BARD (Canvas Assistant) downloads a student's Canvas coursework to their own computer so they can search it and point their own AI tool at it. Everything stays on the user's machine. BARD only reads from Canvas; it never writes to it.

New here? See [GETTING_STARTED.md](GETTING_STARTED.md).

## What
A Canvas Assistant for students/professors to make canvas operations easier, to promote learning and engagement 

## Why
Canvas exposes a lot of information (assignments, due dates, grades, announcements)
but doesn't make it easy to act on quickly. Students juggling multiple courses can
miss deadlines or lose track of what's due, and professors spend time on repetitive
administrative tasks. BARD sits on top of Canvas to surface what matters and
streamline common workflows for both audiences.

## How
BARD uses the Canvas API (read-only) to download assignments, pages, announcements and files, then lets you search them and see what is due next, in your own timezone.
See [docs/Reports/02_Design.md](docs/Reports/02_Design.md)
for the detailed architecture.

## Demo
Link to a demo video or live deployment (add when available).

## Team
- Name — role
- Name — role

## Setup
Instructions for getting the project running locally.

```bash
# clone
git clone <repo-url>
cd CptS_322_BARD

# see code/README.md and code/backend|frontend/README.md for
# component-specific setup instructions
```

## Repository Structure
See [CONTRIBUTING.md](CONTRIBUTING.md) for how we work, and the `docs/` folder for
requirements, design, meeting notes, and project management artifacts.
