# Final Report

## 1. Executive Summary
-

## 2. Objectives vs. Outcomes
-

## 3. What We Built
-

## 4. Challenges & Lessons Learned
* Validation first:
  * For Sprint 2 Part A we wrote the acceptance criteria and the "done when" checks before the code, for every story but one. The re-upload work (S2-19) was built first and got its spec afterwards, when we saw that two other stories depended on it.
  * We also gave the test fake the cases those checks needed (a blocked Files tab, a locked file, a file that changes between syncs).
  * Part A went in as five small pull requests, each based on the one before: shared format (#31), modules and file fallback (#33, merged again as #48), retries and live progress (#49), the coverage report (#50) and re-upload versions (#52).
  * Each pull request was reviewed against its checks, then the stack was run against a real Canvas account (Test Plan TC-1 to TC-7).
  * Review and the real runs still found four gaps: a hidden Files tab showed as ok in the report, module entries did not record which item they point at, quiz entries pointed at the quiz id instead of the assignment BARD saves, and one part of a course that kept failing dropped the whole course instead of showing one error cell. Each was fixed with a test.
  * The last one was found by checking every acceptance criterion against a test before opening the pull request. The real run could not have found it, because nothing failed during that run.
  * The checks, not anyone saying the work was done, were what showed it was right.
* Most gaps sat where one part hands data to another (Part A to the web page, the file work, the report). AGENTS.md now asks every spec to list what it depends on and what it provides.
* Stacked pull requests need to be merged one at a time. #33 was merged into the branch below it seconds after that branch went into main, so its code never reached main and had to go in again as #48. The next pull request can be merged only once its base has switched to main.
* A real run finds what the fake cannot. It showed that an archive built over many syncs keeps links the instructor has since replaced, so "missing" has to mean "Canvas still links it".

## 5. Future Work
-

## 6. Acknowledgements
-
