# S1-02b Course contents: requirements

**Covers:** FR-02, FR-03

**User story.** As a student, I want everything from my courses downloaded in one pass so that my local copy is the whole course and not just the parts that were easy to get.

**Gherkin:** `features/complete_download_of_a_course.feature`, `features/files_linked_inside_a_course.feature`

## Acceptance criteria

- `get_course_items()` follows every next-page link: 47 assignments at 10 per page gives 47
- Assignments, announcements and pages are returned as CourseItems
- Files are found three ways (the Files list, module items of type File, `/files/<id>` links in assignment, page and announcement HTML), each file once
- Files linked from modules, assignments or pages are found even when the Files tab is hidden
- Every Canvas call goes through S1-02a's wrapper helper
- Announcements cover the whole course, not only Canvas's default of the last 14 days, and pages
  come with their bodies (so file links inside them are found)
- A part of the course the instructor switched off (Files tab, Pages, Modules) is skipped and the
  rest of the course is still returned
- A linked file Canvas refuses to describe is still listed, so the sync reports it as missed
  instead of it silently disappearing
- The course syllabus is returned as a Page called "Syllabus" (the syllabus can be the only place
  exam dates are written)
- Dates are timezone-aware UTC, whatever offset Canvas sends
