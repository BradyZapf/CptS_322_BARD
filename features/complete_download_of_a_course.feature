# Behaviour spec. If the behaviour should change, change the requirement first (as a team),
# then this file.
@FR-02 @S1-02b
Feature: Complete download of a course
  As a student
  I want everything from my courses downloaded in one pass
  So that my local copy is the whole course and not just the parts that were easy to get.

  Scenario: A course with more items than one response returns
    Given a course containing 47 assignments
    And the server returns them 10 at a time
    When I run a download
    Then the archive contains 47 assignments for that course

  Scenario: Material that is not published as a list
    Given a course whose exam dates appear only in its syllabus
    And the course publishes no pages and no files
    When I run a download
    Then the archive contains the syllabus text for that course
    And the coverage report does not describe the course as empty
