# Test Plan

## 1. Scope
What will and will not be tested.

## 2. Test Strategy
Unit / integration / end-to-end approach.

## 3. Test Environment
* Unit and integration tests run against a fake Canvas (`tests/fakes.py`) with hand-written data, so no real coursework is in the repo. CI runs them on Ubuntu, Windows and macOS.
* The Part A sync was also run against a real WSU Canvas account (Fall 2026, five courses; first on 2026-10-29, again on 2026-11-03 after review fixes), in a throwaway archive folder that was deleted afterwards. That run only read from Canvas (every request a GET). Its results were compared with an independent archive of the same courses, matched by Canvas id, and files also by size and sha256.

## 4. Test Cases
| ID | Description | Steps | Expected Result | Status |
|----|--------------|-------|------------------|--------|
| TC-1 | Full sync of the current term against real Canvas | `bard sync` with no term, into an empty archive folder | Every file Canvas still links is saved, with the same sha256 as the reference archive | Pass: 276 of 276 files across 5 courses (317 37, 322 48, 172 168, 220 23, 355 0); about 16 minutes, 417 MB |
| TC-2 | Second sync with nothing changed | Run `bard sync` again on the same folder | Nothing is downloaded again, and no earlier-version copies are made (NFR-03) | Pass: 0 saved, all unchanged, about 5 minutes |
| TC-3 | Hidden Files tab | Sync a course whose Files tab answers 403 (CPT_S 317, CPT_S 322) | The tab shows as blocked, with a note that the linked files were still saved | Pass after a fix: every linked file saved; the first run showed the tab as ok, which the 2026-11-03 fix corrected |
| TC-4 | Assignments, announcements, pages, modules and syllabus | Compare the synced items with the reference archive by Canvas id | Same items; assignments match on name, due date and points | Pass: every course matches (for example CPT_S 355: 18 assignments, 3 announcements, the syllabus) |
| TC-5 | A file the instructor forbids | A page links a file that answers 403 | The file is listed as blocked with its reason, not dropped | Pass |
| TC-6 | Renamed or replaced items | A page renamed, or a module file replaced at the same position | The current version is saved; the old one is not reported as missing | Pass: checked live, the old page address redirects to the renamed page |

## 5. Risks & Mitigations
* A reference list built from an older archive overstates what Canvas links today, because an archive keeps old links. Mitigation: count a miss only if Canvas still links the item, and check each miss against Canvas directly.
