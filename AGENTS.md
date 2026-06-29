---
name: "Codecov-Skill-Agent-Guidance"
description: "Repository guidance for the Codecov coverage management skill."
applyTo: "**"
---

# Codecov Skill Guidance

This repository packages the `codecov-management` Codex/open-agent skill. Keep changes focused on the root skill payload and the small repository automation needed to publish it.

## Scope

- Treat `SKILL.md` as the user-facing skill entrypoint.
- Treat `scripts/manage_codecov.py` as the CLI entrypoint.
- Keep helper modules in `scripts/` stdlib-only unless a dependency is explicitly justified and documented.
- Keep `agents/openai.yaml`, `assets/`, `references/`, and `LICENSE.txt` synchronized with the packaged skill.

## Security

- Never put Codecov tokens in command arguments, docs examples, logs, commits, or chat output.
- Prefer token environment variables such as `CODECOV_TOKEN`, `CODECOV_API_TOKEN`, or a caller-specified `--token-env`.
- Use `--dry-run` first for non-GET fallback API calls.
- Do not weaken coverage targets, thresholds, flags, path ignores, or status requirements without evidence from Codecov, local reports, and CI logs.

## Validation

Run the narrowest useful checks after edits:

```powershell
python -m compileall scripts
npm run release:verify
```

For behavior changes, also run the relevant CLI command with `--json` against a safe repository or use `--dry-run` for fallback mutations.

## Style

- Prefer clear argparse surfaces and explicit error messages.
- Keep API response parsing defensive; validate external JSON before indexing nested fields.
- Keep docs examples copy-pasteable in PowerShell.
- Avoid broad repo-template changes unless the task is explicitly about repository automation or packaging.
