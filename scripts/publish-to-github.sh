#!/usr/bin/env bash
set -euo pipefail

# Fallback for environments without GitHub connector write access.
# Run from the project root after extracting the release ZIP.
REPO="${1:-Mrlukahuang/ai-short-drama-factory}"

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required: https://cli.github.com/" >&2
  exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "Run 'gh auth login' in your own terminal first." >&2
  exit 1
fi
if [[ ! -f README.md || ! -d src/drama_factory ]]; then
  echo "Run this script from the extracted project's root directory." >&2
  exit 1
fi
if [[ ! -d .git ]]; then
  git init -b main
  git add .
  git commit -m 'chore: initialize AI short drama factory'
fi
if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "Expected the local main branch; switch to main first." >&2
  exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Uncommitted or untracked files detected. Review and commit your intended changes first." >&2
  git status --short >&2
  exit 1
fi

echo "Target repository: $REPO"
echo "This will push the committed local main branch to a PRIVATE GitHub repository."
read -r -p 'Continue? [y/N] ' confirmation
[[ "$confirmation" == 'y' || "$confirmation" == 'Y' ]] || exit 0

if gh repo view "$REPO" --json nameWithOwner >/dev/null 2>&1; then
  is_private="$(gh repo view "$REPO" --json isPrivate --jq '.isPrivate')"
  if [[ "$is_private" != "true" ]]; then
    echo "Refusing to push: the existing GitHub repository is not private." >&2
    exit 1
  fi
  echo "Found existing private repository."
else
  echo "Repository is not accessible with the current gh account; do not create an accidental duplicate." >&2
  echo "Check the repository name and authentication, or create the private repository in GitHub first." >&2
  exit 1
fi

remote_url="https://github.com/${REPO}.git"
if git remote get-url origin >/dev/null 2>&1; then
  if [[ "$(git remote get-url origin)" != "$remote_url" ]]; then
    echo "origin already points elsewhere; refusing to change it automatically." >&2
    exit 1
  fi
else
  git remote add origin "$remote_url"
fi

# Normal push only: never force-overwrite a remote README or someone else's work.
if ! git push -u origin main; then
  echo "Push was rejected. Check whether the remote contains an initial README or other commits; no force push was attempted." >&2
  exit 1
fi
echo "Published: https://github.com/$REPO"
