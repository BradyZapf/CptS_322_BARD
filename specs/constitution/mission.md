# Mission

BARD downloads a student's Canvas coursework to their own computer so they can search it and
point their own AI tool at it. Everything stays on the user's machine. BARD only reads from
Canvas; it never writes to it.

*(Change this statement only as a team.)*

## Who it is for

Students. (Instructors are out of scope for now.)

| User | How they use BARD |
|---|---|
| Student with no AI tool | the local web page: browse and search (everyone gets this) |
| Student with a coding agent | the agent reads the archive folder directly, or uses `bard search` |
| Student with a desktop AI app | the AI connector (stdio MCP) |
| Student with only a browser chatbot | export a selection as one document and paste it |

## Rules every change must keep

These come from the non-functional requirements (NFR-01..07). A pull request that breaks one is
not merged, however good the feature is.

1. **Read-only.** BARD sends only GET requests to Canvas. Nothing in the code may create,
   change or delete anything in Canvas.
2. **Data-local (NFR-01).** Coursework and the token go nowhere except the user's own computer
   and their own school's Canvas. No analytics, no cloud, no "phone home".
3. **The folder is the interface.** Every original is kept, and every readable thing gets a
   plain-text `.md` copy beside it. The search index is built from those files and can always
   be rebuilt. Anything (an editor, grep, an AI agent) can read the folder.
4. **BARD has no AI inside it.** It never generates answers. Search returns real passages
   with their source. AI is the user's own choice, connected from outside.
5. **Token safety (NFR-06).** The token lives in one file readable only by the user, and only
   `CanvasConnection` uses it. It is never printed, logged or committed.
6. **Works offline after a sync (NFR-02)**, and on Windows, macOS and Linux (NFR-07).
7. **Tests never use a real Canvas account or real Canvas data.** Hand-written fake data only.
8. **Honest reporting.** If something was not downloaded, say what and why (FR-04). "Unknown"
   is not "zero", and "handed in somewhere else" is not "missing".
