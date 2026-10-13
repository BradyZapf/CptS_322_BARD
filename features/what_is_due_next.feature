# Behaviour spec. If the behaviour should change, change the requirement first (as a team),
# then this file.
@FR-07 @S1-03
Feature: What is due next
  As a student taking several courses
  I want one list of upcoming graded work across all of them
  So that I can see what is next without opening each course.

  Scenario: Work from every course in one list
    Given I am enrolled in five courses with graded work due in the next two weeks
    When I open the upcoming work list
    Then the items from all five courses appear in date order

  Scenario: Work that is not handed in through Canvas
    Given a course whose written homework is handed in through a separate tool
    And Canvas therefore holds no submission for it
    When I open the upcoming work list
    Then that item appears with its due date
    And the system does not describe it as missing
