# Test Plan

## 1. Scope
What will and will not be tested.

## 2. Test Strategy
Unit / integration / end-to-end approach.

## 3. Test Environment
* Unit and integration tests run against a fake Canvas (`tests/fakes.py`) with hand-written data, so no real coursework is in the repo. CI runs them on Ubuntu, Windows and macOS.
* The Part A sync was also run against a real WSU Canvas account, read only (every request a GET):
  * 2026-10-29: a full sync of five courses into a throwaway folder, deleted afterwards. Its results were compared with an independent archive of the same courses, matched by Canvas id, and files also by size and sha256.
  * 2026-11-03: three syncs into an existing archive on a laptop, one with each of the last three Part A pull requests (#49, #50, #52), to check the live progress, the coverage report and that nothing was copied by mistake.

## 4. Test Cases
| ID | Description | Steps | Expected Result | Status |
|----|--------------|-------|------------------|--------|
| TC-1 | Full sync of the current term against real Canvas | `bard sync` with no term, into an empty archive folder | Every file Canvas still links is saved, with the same sha256 as the reference archive | 2026-10-29: 276 of the 278 files Canvas linked were saved (317 37 of 37, 322 48 of 49, 172 168 of 168, 220 23 of 24, 355 none), about 16 minutes, 417 MB. The 2 misses were module files (a CPT_S 322 slide deck and a MATH 220 syllabus). By 2026-11-03 those modules pointed at replacement files, and BARD saved them. |
| TC-2 | Second sync with nothing changed | Run `bard sync` again on the same folder | Nothing is downloaded again, and no earlier-version copies are made (NFR-03) | Pass: 0 saved, all unchanged (about 5 minutes on 2026-10-29). On 2026-11-03 three more syncs found every file unchanged and made no earlier-version copies. |
| TC-3 | Hidden Files tab | Sync a course whose Files tab answers 403 (CPT_S 317, CPT_S 322) | The tab shows as blocked, with a note that the linked files were still saved | Pass after a fix. Every linked file was saved both times, but review showed the first version of the report called the tab ok. On 2026-11-03 the report showed both tabs as blocked, with 42 (317) and 50 (322) files saved another way. |
| TC-4 | Assignments, announcements, pages, modules and syllabus | Compare the synced items with the reference archive by Canvas id | Same items; assignments match on name, due date and points | Pass, apart from 2 pages that had been renamed since the reference archive was made (see TC-6). Assignments, announcements, modules and syllabus matched in every course (for example CPT_S 355: 18 assignments, 3 announcements, the syllabus). |
| TC-5 | A file the instructor forbids | A page links a file that answers 403 | The file is listed as blocked with its reason, not dropped | Pass: one MATH 172 file answered 403 on both dates and was listed as blocked with its reason |
| TC-6 | Renamed or replaced items | A page renamed, or a module file replaced at the same position | The current version is saved; the old one is not reported as missing | Pass: checked live, the old page address redirects to the renamed page |
| TC-7 | Quota header | Read one Canvas answer | Canvas sends `X-Rate-Limit-Remaining`, so the quota wait (S2-05) has something to read | Pass: a full quota reads 700.0 and one request cost about 0.08. A normal sync never got near the limit of 100, so the wait itself has only run in the tests. |
| TC-8 | Connect with a saved token (S2-17) | With `BARD_HOME` and `BARD_CONFIG` set to throwaway folders, connect with a real token, then run `bard connect` again | It asks for nothing, makes no call to Canvas, and says "Already connected to", the address, and the replace and disconnect commands | Not run yet |
| TC-9 | Replace with a wrong token (S2-17) | `bard connect --replace` and type a wrong token | Canvas rejects it, and the old token is still saved and still works | Not run yet |
| TC-10 | Saved token no longer accepted (S2-17) | Replace the saved token in the config file with a bad one, then `bard sync` | One message saying the token expired or was removed, with `bard connect --replace`, and no traceback | Not run yet |
| TC-11 | Disconnect (S2-17) | `bard disconnect`, then `bard disconnect` again | First: the token file is gone and the archive is unchanged. Second: "Not connected" | Not run yet |

## 5. Risks & Mitigations
* A reference list built from an older archive overstates what Canvas links today, because an archive keeps old links. Mitigation: count a miss only if Canvas still links the item, and check each miss against Canvas directly.
