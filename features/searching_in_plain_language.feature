# Behaviour spec. If the behaviour should change, change the requirement first (as a team),
# then this file.
@FR-06 @S1-04
Feature: Searching in plain language
  As a student
  I want to search my coursework in plain language and see the passage that answers me
  So that I do not have to remember which file it was in.

  Scenario: A question answered by a passage
    Given my archive contains a syllabus stating the late work policy
    When I search for what happens if I hand work in late
    Then the results include that passage
    And each result names the document and date it came from

  Scenario: A question the archive cannot answer
    Given my archive contains nothing about parking permits
    When I search for where to buy a parking permit
    Then the system reports that nothing in the archive matches
    And the system does not present unrelated passages as answers
