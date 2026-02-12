---
name: pr
description: Create a branch and open a pull request via GitHub CLI.
  Use after changes are committed.
---

# Pull Request

Create a feature branch, push changes, and open a PR using `gh` CLI.

## Prerequisites

- `gh` CLI must be installed and authenticated.
- Changes must already be committed using the commit skill.

## Steps

1. Read the Branch Naming section of CONTRIBUTING.md for the
   naming convention.
2. Create a new branch from the current HEAD following the
   naming convention.
3. Push the branch to the remote.
4. Read .github/pull_request_template.md for the expected PR
   body structure.
5. Construct the PR title following the Conventional Commits
   format documented in CONTRIBUTING.md.
6. Fill in the PR body template based on the committed changes.
7. Open the PR using `gh pr create` targeting the default branch.
8. Display the PR URL.
