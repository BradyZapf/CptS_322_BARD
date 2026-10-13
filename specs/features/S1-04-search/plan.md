# S1-04 Search my coursework: plan

## Files this story touches

- `search_index.py`
- `sync.py`: call `SearchIndex.add_item()` after each item is saved (one line, coordinate with the S1-00 reviewer)

Do not change other files except to wire your code in. If `models.py` needs a change, open a
separate pull request for it first (see AGENTS.md).

## Steps

1. SQLite FTS5 is built into Python: `create virtual table docs using fts5(key UNINDEXED, course, title, body)`.
2. Search with `... where docs match ? order by bm25(docs)`. `snippet(docs, 3, '', '', '...', 20)` gives the passage.
3. Quote each word of the user's query (`"late" "work"`), or FTS5 treats words like AND/OR/NOT and `-` as operators and can crash.
4. Each Passage needs a CourseItem, but CourseItem is abstract. Store the course, title and path in the table and rebuild the result as a `Page(item_id=..., title=..., course_code=..., local_path=..., body=...)`. That is enough for `source()`.
5. Open the database, do the work and close it in each method (`with sqlite3.connect(...) as db:` then `db.close()`). An open connection on Windows stops `erase` from deleting `index.db`.
6. Search first covers assignments, pages and announcements. Text inside PDFs and Word files comes in a later sprint, so do not build extraction here.

## Before you start (agents too)

Explain this story back in two or three sentences, and say which test file proves it. A
misunderstanding should show up in one sentence, not in a hundred lines of code.
