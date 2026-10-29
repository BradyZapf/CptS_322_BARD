# Final Report

## 1. Executive Summary
-

## 2. Objectives vs. Outcomes
-

## 3. What We Built
-

## 4. Challenges & Lessons Learned
* Validation first, then one pass:
  * For Sprint 2 Part A we wrote the acceptance criteria and the "done when" checks for every story before any code.
  * We also gave the test fake the cases those checks needed (a blocked Files tab, a locked file, a file that changes between syncs).
  * With the checks in place, an AI coding assistant built the whole Part A stack in one pass: five pull requests, each based on the one before (shared format, modules and file fallback, retries and live progress, the coverage report, re-upload versions).
  * Each pull request was reviewed against its checks, then the stack was run once against a real Canvas account (Test Plan TC-1 to TC-6), with no gaps found.
  * The checks, not the assistant saying it was done, were what showed the work was right.
* A real run finds what the fake cannot. It showed that an archive built over many syncs keeps links the instructor has since replaced, so "missing" has to mean "Canvas still links it".

## 5. Future Work
-

## 6. Acknowledgements
-
