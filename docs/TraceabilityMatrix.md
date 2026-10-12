# Traceability Matrix

Each requirement, traced to its user story, use case, design classes, acceptance scenarios
and test. An empty Test column means the requirement has not been verified yet. Whether a
test is built or still skipped shows in the `pytest -rs` output, so it is not repeated here.

`scripts/check_traceability.py` (run by CI) fails if a `.feature` file or a test file is missing
from this table, so add a row when you add either.

| Req | User story | Use case | Classes | Gherkin (`features/`) | Test | Spec |
|---|---|---|---|---|---|---|
| FR-01 | Connecting a Canvas account | Connect Canvas account, Verify token | User, CanvasConnection | connecting_a_canvas_account | test_s1_01_connect | S1-01 |
| FR-02 | Complete download of a course | Sync coursework | SyncCoursework, CanvasConnection, Course, CourseItem | complete_download_of_a_course | test_s1_00_sync, test_s1_02b_course_contents | S1-00, S1-02a, S1-02b |
| FR-03 | Files linked inside a course | Collect linked files | CanvasConnection, CourseFile | files_linked_inside_a_course | test_s1_02a_canvas_plumbing, test_s1_02b_course_contents | S1-02a, S1-02b |
| FR-04 | Coverage report | Report coverage | SyncReport | coverage_report | test_s1_00_sync (part) | S1-00 |
| FR-05 | Deadlines in my own timezone | View upcoming work | Assignment | deadlines_in_my_own_timezone | test_s1_03_upcoming | S1-03 |
| FR-06 | Searching in plain language | Search coursework | SearchIndex, Passage, CourseItem | searching_in_plain_language | test_s1_04_search | S1-04 |
| FR-07 | What is due next | View upcoming work | User, Course, Assignment | what_is_due_next | test_s1_03_upcoming | S1-03 |
| FR-08 | Exporting part of the archive | Export coursework | Exporter, CourseItem | exporting_part_of_the_archive |  |  |
| FR-09 | My own AI tool reading the archive | Answer AI tool requests | AiConnector, SearchIndex | my_own_ai_tool_reading_the_archive |  |  |
| FR-10 | Erasing everything | Delete all data | User | erasing_everything | test_s1_05_erase | S1-05 |

| NFR | Checked by |
|---|---|
| NFR-01 Privacy | code review against mission.md rule 2; only `CanvasConnection` makes network calls |
| NFR-02 Offline | search and upcoming work read only local files (tests run with no network) |
| NFR-03 No re-download | test_s1_00_sync::test_unchanged_file_is_not_downloaded_twice |
| NFR-04 Search < 1 s | test_s1_04_search::test_search_is_fast |
| NFR-05 Local interface token | applies to the web page only (stdio MCP has no port) |
| NFR-06 Token file owner-only | test_s1_01_connect::test_token_file_is_owner_only |
| NFR-07 Three systems | CI runs on Ubuntu, Windows and macOS; test_s1_00_sync::test_file_names_are_safe_on_windows |
