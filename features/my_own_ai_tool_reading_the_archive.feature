# NOTE: these scenarios assume an HTTP interface with an access token.
# The team chose a stdio MCP connector instead, which has no token on this path.
# The team should reword them before anyone builds FR-09.
# Behaviour spec. If the behaviour should change, change the requirement first (as a team),
# then this file.
@FR-09 @backlog
Feature: My own AI tool reading the archive
  As a student running my own AI tool
  I want it to read my archive directly
  So that I do not have to paste anything myself.

  Scenario: A request carrying the access token
    Given my AI tool holds the access token the system issued
    When it asks the local interface for an assignment
    Then the interface returns that assignment

  Scenario: Another program on the same computer
    Given a program on my computer that does not hold the access token
    When it asks the local interface for an assignment
    Then the interface refuses the request
    And the interface returns no coursework
