---
name: pr
description: Create a branch, push, and open a pull request
---

# Pull Request

Create a properly formatted pull request targeting `main`.

## Steps

1. **Create branch** — If not already on a feature branch, create one:
   ```
   feature/<description>   # New features
   fix/<description>       # Bug fixes
   chore/<description>     # Maintenance
   docs/<description>      # Documentation
   ```
   Use kebab-case for the description.

2. **Push branch** — Push with upstream tracking:
   ```bash
   git push -u origin <branch-name>
   ```

3. **Create PR** — Use `gh pr create` with:
   - **Title**: Conventional Commits format (`<type>: <description>`)
   - **Body**: Summary + Test Plan using the repo's PR template
   - **Target**: `main`

   ```bash
   gh pr create --title "<type>: <description>" --body "$(cat <<'EOF'
   ## Summary
   - <what changed and why>

   ## Test Plan
   - [ ] `just lint` passes
   - [ ] `just test-unit` passes
   EOF
   )"
   ```

4. **Return PR URL** — Share the URL so the user can review.

## Rules

- One logical change per PR
- PR title must be Conventional Commits format (it becomes the squash commit message)
- Always target `main`
