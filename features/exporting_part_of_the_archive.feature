# Behaviour spec. If the behaviour should change, change the requirement first (as a team),
# then this file.
@FR-08 @backlog
Feature: Exporting part of the archive
  As a student whose only AI tool is a browser chatbot
  I want to export part of my coursework as one document
  So that I can paste it into a conversation.

  Scenario: Exporting one course
    Given a course containing 24 archived items
    When I export that course
    Then the system produces one document containing their text
    And the system shows me its size before I copy it

  Scenario: A selection larger than the limit
    Given a selection whose text is larger than the limit I set
    When I export it
    Then the system tells me the selection is too large
    And the system offers to narrow the selection or split it into numbered parts
