# S1-02b Course contents: plan

## Files this story touches

- `canvas_connection.py`: `get_course_items()` and its private helpers
- `code/backend/tests/test_s1_02b_course_contents.py`: the tests
- `code/backend/tests/fakes.py`: new fake Canvas JSON builders (pages, announcements, files,
  module items); nothing existing changes

Do not change other files except to wire your code in. If `models.py` needs a change, open a
separate pull request for it first (see AGENTS.md).

## Steps

1. You can start the same day as S1-02a, before its helpers merge: call canvasapi directly at first, then switch each call to S1-02a's `_call` helper once it lands. Never catch canvasapi exceptions yourself.
2. Use canvasapi, which follows pages for you: `c = canvas.get_course(course.course_id)` (one GET for the course), then `c.get_assignments()`, `c.get_pages()`, `c.get_files()`, `c.get_modules()`, and `canvas.get_announcements(context_codes=[f"course_{course.course_id}"])`. These are exactly the URLs the test fakes. Pass `include=["body"]` to `get_pages()` (the plain list has no bodies) and `start_date`/`end_date` to `get_announcements()` (without them Canvas sends only the last 14 days). Ask for the course with `include=["syllabus_body"]` and return the syllabus as a Page.
2b. Read each list with `_call(lambda: list(...))`. A list that answers `NotAvailable` (that part of the course is switched off) counts as empty; do not catch `TokenRejected` or `CanvasUnreachable`.
3. Map each Canvas object to our models: an assignment JSON -> `Assignment(item_id=a['id'], title=a['name'], due_date=<parsed due_at>, ...)`.
4. Find files three ways: the Files list, module items of type File, and `/files/<id>` links inside assignment, page and announcement HTML. Fetch each by id with `canvas.get_file(id)`, and keep each file id only once. (Attachments on your own submissions are a fourth source, but leave them for a later sprint: the test does not fake that URL.)

## Before you start (agents too)

Explain this story back in two or three sentences, and say which test file proves it. A
misunderstanding should show up in one sentence, not in a hundred lines of code.
