# Behaviour spec. If the behaviour should change, change the requirement first (as a team),
# then this file.
@FR-04 @backlog
Feature: Coverage report
  As a student
  I want to be told what could not be downloaded and why
  So that I know when to go and look in Canvas myself.

  Scenario: A partial course is shown as partial
    Given a download in which one course returned its files and another did not
    When I open the coverage report
    Then the report shows the first course as complete
    And the report shows the second as partial, with the reason

  Scenario: A switched-off feature is not a failure
    Given a course whose pages have been turned off by the instructor
    When I open the coverage report
    Then the report shows pages as unavailable for that course
    And the report does not show the course as failed
