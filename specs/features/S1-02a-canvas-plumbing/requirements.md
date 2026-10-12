# S1-02a Canvas plumbing: requirements

**Covers:** FR-02, FR-03, NFR-06

**User story.** As a student, I want BARD to cope with Canvas being slow, strict or partly switched off so that one bad answer does not lose or hide the rest of my course.

**Gherkin:** `features/complete_download_of_a_course.feature`, `features/files_linked_inside_a_course.feature`. This story is the foundation under them: S1-02b builds on it.

## Acceptance criteria

- One private helper builds the canvasapi client from the URL and token
- One private helper wraps every Canvas call and turns errors into BARD's own: 401 -> `TokenRejected`; 403 or 404 -> `NotAvailable(reason)`
- 429, a 403 whose body says "rate limit", and 5xx wait and retry (a few tries, growing waits) before giving up
- Timeouts and connection errors are reported as "broken", never as "forbidden" (forbidden is normal, broken is not)
- The token never appears in any error message
- `get_courses(term)` returns the user's courses for that term (current term by default). A course with no end date is still synced
- `fetch_file()` raises `NotAvailable("locked by the instructor")` when Canvas gives no download URL
- Only GET requests are ever sent
