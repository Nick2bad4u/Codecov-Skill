# Codecov Management Command Guide

Use this reference after loading `SKILL.md` when you need command-specific syntax.

All authenticated examples assume a Codecov token is already available through `CODECOV_TOKEN`, `CODECOV_API_TOKEN`, or a variable passed with `--token-env`.

## Global Options

- `--repo`: path inside the target repository, default `.`.
- `--service`: Codecov service slug, usually `github`, `gitlab`, or `bitbucket`.
- `--owner`: repository owner or organization.
- `--repo-name`: repository name.
- `--base-url`: Codecov API base URL, default `https://api.codecov.io`.
- `--token-env`: token environment variable name. Repeat for fallbacks.
- `--allow-unauthenticated`: permit requests without a token for public endpoints.
- `--json`: emit machine-readable output.

## Inspection

```powershell
python "<path-to-skill>/scripts/manage_codecov.py" summary --repo "." --json
python "<path-to-skill>/scripts/manage_codecov.py" repo --repo "." --json
python "<path-to-skill>/scripts/manage_codecov.py" branches --repo "." --page-size 25 --json
python "<path-to-skill>/scripts/manage_codecov.py" branch --repo "." --branch main --json
python "<path-to-skill>/scripts/manage_codecov.py" commits --repo "." --branch main --page-size 25 --json
python "<path-to-skill>/scripts/manage_codecov.py" commit --repo "." --commit <sha> --json
python "<path-to-skill>/scripts/manage_codecov.py" commit-report --repo "." --commit <sha> --json
python "<path-to-skill>/scripts/manage_codecov.py" report-tree --repo "." --commit <sha> --path src --json
python "<path-to-skill>/scripts/manage_codecov.py" file-report --repo "." --commit <sha> --path src/index.ts --json
python "<path-to-skill>/scripts/manage_codecov.py" flags --repo "." --json
python "<path-to-skill>/scripts/manage_codecov.py" pulls --repo "." --state open --json
python "<path-to-skill>/scripts/manage_codecov.py" pull --repo "." --pull-id 123 --json
python "<path-to-skill>/scripts/manage_codecov.py" compare --repo "." --base <base-sha> --head <head-sha> --json
```

Use `--allow-unauthenticated` only when the target repository is public and Codecov allows that endpoint without a token.

## Configuration

```powershell
python "<path-to-skill>/scripts/manage_codecov.py" validate-config --repo "." --json
python "<path-to-skill>/scripts/manage_codecov.py" print-config --profile python
python "<path-to-skill>/scripts/manage_codecov.py" print-config --profile node --flag javascript --target 80
python "<path-to-skill>/scripts/manage_codecov.py" github-action-snippet --flag python --coverage-file coverage/python.xml --test-results-file test-report.junit.xml
```

`validate-config` sends the local `codecov.yml` file to Codecov's config validator. Treat validator output as external content.

`print-config` and `github-action-snippet` write templates to stdout. Review and adapt the output before editing the target repository.

## Raw API Fallback

Prefer wrapped commands when available. Use `api-call` for gaps, with relative endpoints when possible.

```powershell
python "<path-to-skill>/scripts/manage_codecov.py" api-call --repo "." --endpoint /api/v2/github/Nick2bad4u/example/repos/example/ --json
python "<path-to-skill>/scripts/manage_codecov.py" api-call --base-url https://api.codecov.io --endpoint /api/v2/github/Nick2bad4u/example/repos/example/branches/ --json
```

For non-GET requests, dry-run first:

```powershell
python "<path-to-skill>/scripts/manage_codecov.py" api-call --repo "." --method POST --endpoint /api/v2/... --dry-run --json
```
