# Behaviour spec. If the behaviour should change, change the requirement first (as a team),
# then this file.
@FR-10 @S1-05
Feature: Erasing everything
  As a student who has finished with BARD
  I want to erase everything it has stored
  So that nothing of mine is left on the machine.

  Scenario: Erasing the archive and the token
    Given an archive containing my coursework and a stored Canvas token
    When I confirm that I want to erase everything
    Then the archive is removed from my computer
    And the stored token is removed
    And the system tells me how to revoke that token in Canvas

  Scenario: Something the system cannot remove
    Given an archive containing a file that is open in another program
    When I erase everything
    Then the system names what it could not remove
    And the system does not report the erase as complete
