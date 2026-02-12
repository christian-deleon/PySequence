---
name: commit
description: Stage and commit changes following project conventions.
  Use after all quality checks pass.
---

# Commit

Stage and commit changes using the conventions defined in
CONTRIBUTING.md.

## Prerequisites

- Run the validate skill first. All checks must pass.

## Steps

1. Read the Commit Conventions section of CONTRIBUTING.md for
   the format rules.
2. Review the staged and unstaged changes to understand what
   was changed.
3. Group changes into logical units. Each commit should represent
   one coherent change. If changes span multiple concerns (e.g., a
   bug fix and a refactor), they should be separate commits.
4. For each logical group:
   a. Determine the appropriate commit type and scope.
   b. Construct a commit message that follows the documented format.
   c. Stage only the files belonging to that group.
   d. Commit with the constructed message.
5. Confirm all commits were created and display the messages.
