---
name: commit
description: Stage changes and create a Conventional Commits message
---

# Commit

Stage changes and create a commit with a Conventional Commits message.

## Steps

1. **Review changes** — Run `git status` and `git diff` to understand what changed.

2. **Stage specific files** — Add files individually with `git add <file>`. Never use `git add -A` or `git add .` to avoid accidentally staging secrets or generated files.

3. **Craft commit message** — Write a Conventional Commits message:
   ```
   <type>: <description>
   ```
   Types: `feat`, `fix`, `chore`, `docs`, `ci`, `test`, `refactor`

   - Keep the description concise (under 72 characters)
   - Focus on *why*, not *what*
   - Use imperative mood ("add feature" not "added feature")

4. **Commit** — Create the commit and verify with `git status`.

## Rules

- Never commit `.tokens.json`, `.env`, credentials, or secrets
- Never use `--no-verify` unless explicitly requested
- Never amend previous commits unless explicitly requested
- If a pre-commit hook fails, fix the issue and create a NEW commit
