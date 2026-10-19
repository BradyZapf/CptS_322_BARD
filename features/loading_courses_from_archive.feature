# Behaviour spec. If the behaviour should change, change the requirement first (as a team),
# then this file.
@NFR-02 @S1-03a
Feature: Loading courses from the archive
  As a student who has already synced their courses
  I want BARD to read my assignments back from the archive folder
  So that commands like bard due work without connecting to Canvas again.

  Scenario: Archive with multiple course folders
    Given the archive folder contains two course subfolders
    And each subfolder has an assignments directory with one assignment file
    When load_courses is called
    Then self.courses contains two courses
    And each course has one assignment in its items list

  Scenario: Assignment with a known due date
    Given an assignment file whose Due line holds a UTC timestamp
    When load_courses is called
    Then that assignment has a timezone-aware due_date matching the timestamp

  Scenario: Assignment with no due date
    Given an assignment file whose Due line reads "no due date"
    When load_courses is called
    Then that assignment has due_date set to None

  Scenario: Empty or missing archive
    Given the archive folder does not exist
    When load_courses is called
    Then self.courses is empty
    And no exception is raised

  Scenario: bard due reads from the archive without re-syncing
    Given the archive contains upcoming assignments
    And self.courses is empty at the start of list_upcoming_work
    When list_upcoming_work is called
    Then load_courses is called automatically
    And the returned list contains the upcoming assignments from the archive
