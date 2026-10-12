# Behaviour spec. If the behaviour should change, change the requirement first (as a team),
# then this file.
@FR-01 @S1-01
Feature: Connecting a Canvas account
  As a student setting up BARD
  I want to connect my Canvas account once
  So that I do not have to configure it again.

  Scenario: Connecting for the first time
    Given I have not yet connected a Canvas account
    And I have created a personal access token in Canvas
    When I enter my school's Canvas address and that token
    Then the system stores both on my own computer
    And the system lists the courses I am enrolled in

  Scenario: A token Canvas does not accept
    Given I enter a token that Canvas rejects
    When the system tries to list my courses
    Then the system tells me Canvas rejected the token
    And the system does not store that token
