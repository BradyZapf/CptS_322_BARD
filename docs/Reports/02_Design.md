# Design

## 1. Architecture Overview
High-level system diagram and description.

## 2. Components
| Component | Responsibility |
|-----------|-----------------|
| | |

## 3. Data Model
Description of key entities and relationships.

## 4. Interfaces / APIs
Description of key interfaces between components.

## 5. Technology Stack
-

## 6. Design Decisions & Trade-offs
* BARD only reads from Canvas. Every call is a GET, and the token never leaves `CanvasConnection`, which removes it from any message it passes on.
* A part of a course the instructor switched off (a hidden Files tab, Pages turned off) is reported as blocked, not as an error. Files and pages are still found through modules and through `/files/<id>` links in assignment, page, announcement and syllabus text. A link is followed only when it is relative or on the same Canvas, so a link to another site never makes BARD ask for an unrelated file.
* A file counts as missing only if Canvas still links it today. A page or module that the instructor edited to point at a new copy does not leave the old copy as a gap.
* When an instructor re-uploads a file, BARD keeps the earlier version beside the new one, and a failed write leaves the old copy untouched.
* A sync with no term set pulls every active enrollment, including non-class hub courses (for example the advising and resource hubs). That is on purpose: they hold things a student uses.
* Discussions, the user's own submission files and text from PDF and Word files are separate stories (S2-18, S2-12, S2-10), not part of the Part A sync.
