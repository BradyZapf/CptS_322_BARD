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
* BARD only reads from Canvas: every call is a GET, and the token stays inside `CanvasConnection` (NFR-01, S2-02)
* A part of a course the instructor switched off, such as a hidden Files tab, is reported as blocked, not as an error (S2-03, FR-04)
* Files and pages are still found through modules and `/files/<id>` links in assignment, page, announcement and syllabus text (S2-02, FR-03)
* A saved token is replaced only after Canvas accepts the new one, so a failed `connect --replace` keeps the old one, and `disconnect` removes the token and never the archive (S2-17, FR-01)
* When Canvas stops accepting the token partway through a sync, the sync stops with one message saying how to put in a new token, and keeps what it already saved (S2-17, FR-01)
* A link is followed only when it is relative or on the same Canvas, so a link to another site never makes BARD ask for an unrelated file (FR-03)
* A file counts as missing only if Canvas still links it today, so a page the instructor edited to point at a new copy leaves no gap (S2-03, FR-04)
* When an instructor re-uploads a file, BARD keeps the earlier version beside the new one, and a failed write leaves the old copy untouched (S2-19, FR-03)
* A sync with no term set pulls every active enrollment, including non-class hub courses such as the advising and resource hubs, because they hold things a student uses (FR-02)
* The user's own submission files and text from PDF and Word files are separate stories, not part of the Part A sync (S2-12, S2-10). Discussions moved to the product backlog for Sprint 3 (PB-07)
* **Proposed, pending team approval (S3-12):** scanned PDFs are read with Tesseract, through `pytesseract` and `pypdfium2`, as an optional `pip install .[ocr]` extra plus the Tesseract program. In a bake-off against RapidOCR 3.10, both found 97 to 100% of the words on hand-made scans. Tesseract was faster on every file: 0.3 to 1.6 s a page against 10 to 30 s on one laptop, with noisy timings. It also read two-column pages in the right order and adds about 24 MB from pip instead of about 280 MB. RapidOCR was better on bad photocopies and numbered lists, and needs no separate install. Installing Tesseract (its own size not measured): the UB Mannheim installer on Windows, `brew install tesseract` on macOS, `sudo apt install tesseract-ocr` on Linux, each with the English data. Without OCR installed, BARD works exactly as before. Full results: `specs/features/S3-12-ocr/notes.md` (FR-06, NFR-07)
