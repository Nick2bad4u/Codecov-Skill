# Security Policy

## Supported scope

This repository contains automation and helper scripts for Codecov coverage inspection and setup.

Security-sensitive areas include:

- credential/token handling
- fallback API calls that can use non-GET methods
- workflow automation that can post comments or update repository state

## Reporting a vulnerability

If you discover a vulnerability, please avoid opening a public issue with exploit details.

Instead, contact the maintainer privately (for example via GitHub security reporting or direct private channel) and include:

1. affected file(s) / workflow(s)
2. reproducible steps
3. impact assessment
4. any suggested mitigation

## Secret handling rules

- Never hardcode Codecov tokens.
- Never include tokens in command arguments.
- Use environment variables (e.g. `CODECOV_TOKEN`).
- Prefer secret manager retrieval into environment variables.

PowerShell example:

```powershell
$env:CODECOV_TOKEN = Get-Secret CODECOV_TOKEN_TYPEFEST -AsPlainText
```

## Operational safety

- Use `--dry-run` for non-GET fallback API calls before applying changes.
- Verify target service, owner, repository, and base URL before running fallback calls.
- Re-check state after changes with `summary`, `repo`, `commits`, `flags`, or the relevant detail command.
