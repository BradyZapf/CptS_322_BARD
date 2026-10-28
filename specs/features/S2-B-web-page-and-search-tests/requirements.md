# S2-B Local web page and search tests: requirements

**Covers:** FR-06, NFR-05

**User story.** As a student, I want to open my courses in a browser on my own computer and search them there, so that I can see what BARD downloaded without typing commands.

**Gherkin:** `features/searching_in_plain_language.feature`. The page itself has no behaviour spec yet.

Items: S2-06 to S2-09, see `docs/ProjectManagement/SprintBacklog.md`.

## S2-06 Local web page: course list and item view

### Acceptance criteria

- The page runs on the user's own computer and answers only requests from that computer
- The address carries a secret that is new every time the page starts
- The first page lists every course in the archive
- Opening a course lists its items: assignments, pages, announcements and files
- The items are grouped by module, in the order of the modules, using the modules saved by S2-02; items that are in no module are listed after them
- Opening an item shows its text, read from the .md copy the sync saved
- An empty archive shows "nothing downloaded yet" and not an error
- The page only reads the archive folder and makes no calls to Canvas or the internet
- Flask is added to the dependencies in `pyproject.toml` (it is already the tech stack's choice)
- The page's tests run in CI on Ubuntu, Windows and macOS

## S2-07 Search box on the web page

### Acceptance criteria

- The search box uses `SearchIndex.search()`, not a second search
- Each result shows the course and the title of the item it came from, and links to that item
- An empty search, a lone quote, or a word like AND shows a message and does not crash
- A search with no match says nothing matched and shows no unrelated passages

## S2-08 Tests for search

Carried over from Sprint 1 as [#13](https://github.com/BradyZapf/CptS_322_BARD/issues/13). The tests go in `code/backend/tests/test_s1_04_search.py`.

### Acceptance criteria

- Adding the same page twice replaces it: the old text is not found and the new text is
- The best match comes first: of two pages that both mention a word, the one that mentions it more often is listed first
- Odd queries do not crash: `late AND -work`, a single `"` and an empty query each return a list
- A page and an announcement with the same course and item id can both be found
- A sync indexes what it saves: after a sync with the fake connection, searching for a word from the fake syllabus finds it
- The limit is respected: `limit=1` returns one result

## S2-09 Basic web security tests for the page

### Acceptance criteria

- Searching for SQL injection text such as `' OR 1=1 --` or `"; DROP TABLE docs; --` returns normal results or none, and every item is still findable afterwards
- An item address containing `../`, plain or encoded, is refused and nothing outside the archive is served
- A title such as `<script>alert(1)</script>` is shown as plain text and does not run
- A request without the right secret in the address is refused
- A POST, PUT or DELETE is refused, because the page only reads
