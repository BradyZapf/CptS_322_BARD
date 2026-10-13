# Behaviour spec. If the behaviour should change, change the requirement first (as a team),
# then this file.
@FR-03 @S1-02b
Feature: Files linked inside a course
  As a student
  I want the files linked inside my course collected as well,
  So that my archive is not limited to whatever a single list happens to show.

  Scenario: Files that appear only inside modules
    Given a course whose file list is not shown in the course navigation
    And the course modules link to 23 files
    When I run a download
    Then the archive contains those 23 files
    And the coverage report records where they were found

  Scenario: No files linked anywhere in the course
    Given a course whose file list is not shown in the course navigation
    And no module, page or assignment in that course links to a file
    When I run a download
    Then the coverage report records that course's file count as unknown
    And the coverage report does not record it as zero
