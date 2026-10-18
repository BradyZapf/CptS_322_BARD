# Sprint 1 Retrospective

**Date:** 2026-10-18  **Attendees:** Ryan Brenner, for the team

## What went well
- The code was scaffolded up front and the work was split well, so four people could build in parallel without editing the same files.
- Every story had a written spec and its own test file.
- Tests used fake Canvas data only, so no real coursework reached the repo.
- CI on Windows, Mac and Linux passed on the pull requests.
- Splitting S1-02 into plumbing (S1-02a) and contents (S1-02b) let the foundation merge first, and the dependent story built on it.
- Six of the seven Sprint 1 items merged: S1-00, S1-01, S1-02a, S1-02b, S1-04, S1-05.

## What did not go well
- Getting started was hard. We were still learning Git and our software, so the first pull requests took a long time, and the repo had no code until 10/12.
- Reviews were slow and not as interactive as we would like. We planned to require an approval on main but never turned the protection on, so some pull requests merged with no review, and the reviewed ones got an approval more than a conversation.
- The board did not always match the code. The S1-03 issue was closed with no code on main.
- The first AGENTS.md wording made an AI agent over-escalate a small decision to the team. PR #12 fixed it.

## How the process can improve

| # | Action item | Owner | How we will know it worked |
|---|---|---|---|
| 1 | Spend the first days of the sprint getting everyone set up and comfortable with Git and the tools | Whole team | the first pull request opens within 3 days of sprint start |
| 2 | Turn on branch protection for main, and review every pull request within 24 hours with comments and a quick conversation, not just an approval | Whole team | no pull request merges without a review, and each has at least one review comment |
| 3 | Close an issue only when its pull request is merged | Whole team | the board matches `git log` |

## Review meeting outcome

Completed and demonstrated: S1-00 skeleton and sync, S1-01 connect, S1-02a Canvas plumbing, S1-02b course contents, S1-04 search, S1-05 erase.
Not completed, and why: S1-03 upcoming work moves to Sprint 2.
