# Codecov Skill

[![Latest GitHub release.](https://flat.badgen.net/github/release/Nick2bad4u/Codecov-Skill?color=cyan)](https://github.com/Nick2bad4u/Codecov-Skill/releases) [![GitHub stars.](https://flat.badgen.net/github/stars/Nick2bad4u/Codecov-Skill?color=yellow)](https://github.com/Nick2bad4u/Codecov-Skill/stargazers) [![GitHub forks.](https://flat.badgen.net/github/forks/Nick2bad4u/Codecov-Skill?color=green)](https://github.com/Nick2bad4u/Codecov-Skill/forks) [![GitHub open issues.](https://flat.badgen.net/github/open-issues/Nick2bad4u/Codecov-Skill?color=red)](https://github.com/Nick2bad4u/Codecov-Skill/issues) [![GitHub PRs.](https://flat.badgen.net/github/open-prs/Nick2bad4u/Codecov-Skill?color=orange)](https://github.com/Nick2bad4u/Codecov-Skill/pulls?q=sort%3Aupdated-desc+is%3Apr+is%3Aopen) [![GitHub license](https://flat.badgen.net/github/license/Nick2bad4u/Codecov-Skill?color=purple)](https://github.com/Nick2bad4u/Codecov-Skill/blob/main/LICENSE) [![Codecov.](https://flat.badgen.net/codecov/github/Nick2bad4u/Codecov-Skill?color=blue)](https://codecov.io/gh/Nick2bad4u/Codecov-Skill) [![Repo Checks.](https://flat.badgen.net/github/checks/nick2bad4u/Codecov-Skill?color=green)](https://github.com/Nick2bad4u/Codecov-Skill/actions)

An open-agent skill for inspecting and managing **Codecov** coverage, API data, upload setup, and repository configuration.

This repository provides:

- a reusable `codecov-management` skill (`skills/codecov-management/SKILL.md`)
- a Python CLI helper to inspect Codecov repositories and validate setup
- GitHub automation for CI, Codecov uploads, and release packaging

---

## What this skill can do

With a Codecov token in an environment variable, you can:

- summarize repository coverage state from Codecov
- inspect branches, commits, commit reports, report trees, file coverage, flags, and pull requests
- compare two commits through the Codecov API
- validate a local `codecov.yml`
- generate starter `codecov.yml` and GitHub Actions upload snippets
- fall back to direct API calls for unsupported Codecov endpoints

> The helper is repository-agnostic: pass `--repo` to any local checkout, or pass explicit `--service`, `--owner`, and `--repo-name`.

---

## Repository layout

```text
skills/
  codecov-management/
    SKILL.md
    LICENSE.txt
    agents/
      openai.yaml
    assets/
      codecov-management-small.svg
      codecov-management.svg
    references/
      command-guide.md
      codecov-setup.md
    scripts/
      manage_codecov.py
      codecov_manage_api.py
      codecov_manage_common.py
      codecov_manage_project.py
      codecov_manage_render.py
README.md
CONTRIBUTING.md
SECURITY.md
CHANGELOG.md
```

---

## Agent compatibility

This package uses the shared skills layout: `skills/codecov-management/SKILL.md` with its bundled `agents/`, `assets/`, `references/`, and `scripts/` directories underneath the skill folder. That shape lets `npx skills` pull the complete payload instead of discovering only a root `SKILL.md`.

Use `--agent universal` for agents that consume the shared `.agents/skills` layout. Use `--agent "*"` only when you intentionally want to install to every supported agent directory.

```powershell
npx skills add Nick2bad4u/Codecov-Skill -g --agent universal -y
npx skills add Nick2bad4u/Codecov-Skill -g --agent "*" -y
npm install --save-dev codecov-management-skill
npx skills experimental_sync --agent universal -y
```

OpenAI-specific display metadata lives in `skills/codecov-management/agents/openai.yaml`. The portable skill contract is `skills/codecov-management/SKILL.md` plus the referenced `assets/`, `references/`, and `scripts/` files in that same skill folder.

---

## Publishing

The skill is packaged for GitHub releases and npm as `codecov-management-skill`.

Verify the package locally before publishing:

```powershell
npm run release:verify
npm publish --access public --provenance
```

GitHub Actions publishes with npm OIDC trusted publishing using `npm publish --access public --provenance`. Configure the npm package trusted publisher for repository `Nick2bad4u/Codecov-Skill` and workflow `.github/workflows/release-skill.yml` before the first publish.

---

## Quick start

### 1) Prerequisites

- Python 3.14 for the strict local validation setup
- A Codecov API token exported to an environment variable for private repositories or authenticated endpoints

### 2) Set your token

#### PowerShell

```powershell
$env:CODECOV_TOKEN = "<your-token>"
```

#### Bash

```bash
export CODECOV_TOKEN="<your-token>"
```

### 3) Run the helper

From repository root:

```powershell
python "skills/codecov-management/scripts/manage_codecov.py" summary --repo "." --json
```

Public repository read attempt without a token:

```powershell
python "skills/codecov-management/scripts/manage_codecov.py" repo --repo "." --allow-unauthenticated --json
```

Validate local Codecov configuration:

```powershell
python "skills/codecov-management/scripts/manage_codecov.py" validate-config --repo "." --json
```
