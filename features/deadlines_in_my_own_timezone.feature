# Behaviour spec. If the behaviour should change, change the requirement first (as a team),
# then this file.
@FR-05 @S1-03
Feature: Deadlines in my own timezone
  As a student
  I want deadlines shown in my own timezone
  So that I do not miss work that appears to be due the following day.

  Scenario: A deadline stored in a different timezone
    Given an assignment the server records as due at 06:59 on 21 September UTC
    And my computer is set to Pacific time
    When I view that assignment
    Then the deadline reads 23:59 on 20 September

  Scenario: The same deadline after I travel
    Given I viewed that deadline while my computer was set to Pacific time
    When I set my computer to Eastern time and view it again
    Then the deadline is shown in Eastern time
    And the deadline still refers to the same moment
