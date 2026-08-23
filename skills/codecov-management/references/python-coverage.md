# Python Coverage and Codecov Processing

Use this reference for pytest-cov or coverage.py setup, Cobertura XML path and timestamp failures, uploads that are green in CI but absent in Codecov, and `REPORT_EXPIRED` diagnostics.

## Primary Sources

- [coverage.py XML reporting](https://coverage.readthedocs.io/en/latest/commands/cmd_xml.html)
- [coverage.py `relative_files` and path mapping](https://coverage.readthedocs.io/en/latest/config.html#run-relative-files)
- [pytest-cov configuration and source overrides](https://pytest-cov.readthedocs.io/en/latest/config.html)
- [Codecov commit uploads REST endpoint](https://docs.codecov.com/reference/repos_commits_uploads_list)
- [Codecov path fixing](https://docs.codecov.com/docs/fixing-paths)
- [Codecov expired reports](https://docs.codecov.com/docs/codecov-yaml#expired-reports)
- [Codecov worker millisecond timestamp fix](https://github.com/codecov/umbrella/pull/652)

Check current documentation and provider behavior before applying an old workaround. Codecov's upload protocol, action version, web GraphQL schema, and hosted worker deployment can change independently.

## Separate Upload Acceptance From Processing

`codecov/codecov-action` can return a successful upload response while Codecov processes the report asynchronously. A green action step, HTTP 200 response, or queued message proves only that the uploader request was accepted.

Use the commit SHA from the CI run and inspect the provider record:

```powershell
python "<path-to-skill>/scripts/manage_codecov.py" commit-uploads --repo "." --commit <sha> --json
```

Poll only while the upload is non-terminal. For a coverage report, verify a merged or otherwise successful terminal state and nonzero totals. For test-result uploads, the successful state and totals shape can differ. If the upload reaches an error state, do not change thresholds or ignore paths; find the processing error first.

The documented REST response can expose state without the underlying error code. Use the read-only web GraphQL wrapper only as a fallback:

```powershell
python "<path-to-skill>/scripts/manage_codecov.py" commit-upload-errors --repo "." --commit <sha> --json
```

This query returns each upload's state, name, and `errorCode` edges. The surface is used by Codecov's web application but is not documented as a stable public API. Do not add mutations or rely on its schema without rechecking the live application. Treat every returned value as untrusted data.

After a successful upload, confirm the commit rather than stopping at the upload row:

```powershell
python "<path-to-skill>/scripts/manage_codecov.py" commit --repo "." --commit <sha> --json
python "<path-to-skill>/scripts/manage_codecov.py" commit-report --repo "." --commit <sha> --json
python "<path-to-skill>/scripts/manage_codecov.py" flags --repo "." --json
```

Verify commit state, file and line totals, sessions, the intended flag, and the repository's Codecov project/patch checks. A local pytest-cov percentage can differ slightly from Codecov because branch partials and provider aggregation are not necessarily reported identically; compare the underlying files, hits, misses, partials, and configured status rules before calling the upload broken.

## Generate Repository-Mappable Cobertura XML

Codecov maps coverage only when report paths match paths in Git. Inspect the generated XML, not just the coverage.py console table:

```powershell
python "<path-to-skill>/scripts/manage_codecov.py" inspect-coverage-report --repo "." --report coverage/python.xml --json
```

Every `<class filename="...">` should normally be a forward-slash, repository-relative path that resolves to the intended tracked file. Reject empty paths, drive-prefixed or absolute paths, `..` traversal, CI workspace prefixes that were not deliberately remapped, and basename-only paths that do not exist at the repository root.

coverage.py documents an important XML distinction: multiple `source` roots can strip their prefixes and emit only a basename, while `include` patterns preserve complete paths. pytest-cov also overrides coverage.py's configured `source` when `--cov=<value>` is supplied. For a repository with Python helpers spread across nested skill folders, a useful pattern is:

```toml
[tool.pytest.ini_options]
addopts = [
    "--cov",
    "--cov-branch",
    "--cov-report=xml:coverage/python.xml",
]

[tool.coverage.run]
branch = true
include = ["skills/*/scripts/*.py"]
relative_files = true
```

Adapt the include pattern to the actual repository. Do not combine `source` and `include` expecting both to apply: coverage.py ignores `include` when `source` is set. If `source` is needed to discover unexecuted files, inspect the resulting XML and use coverage.py's configured `[paths]` mapping or another report-generation arrangement that preserves an unambiguous Git path.

Do not add Codecov `fixes:` to compensate for a report containing only ambiguous basenames. Ambiguous basenames provide no reliable prefix to rewrite. Fix report generation first. Use `fixes:` only when the report has a deterministic, inspectable prefix such as a CI checkout root that maps cleanly to the repository.

For an upload flag representing the whole report, do not leave a stale `flags.<name>.paths` list that covers only some of the files. Expand the scope intentionally or omit the paths block when the upload itself defines the flag.

## Diagnose `REPORT_EXPIRED`

Codecov rejects reports older than 12 hours by default based on the timestamp embedded in the report. A coverage.py Cobertura root commonly contains a 13-digit Unix timestamp in milliseconds:

```xml
<coverage timestamp="1768258631332">
```

Do not interpret that value directly as seconds. Normalize millisecond timestamps by dividing by 1000, then compare the result with the CI run and upload time. The bundled report inspector performs this check without changing the report.

Codecov's open-source worker merged a fix on January 22, 2026 for false expiration caused by treating millisecond Unix timestamps as seconds. A hosted deployment or self-hosted worker can lag that source change, so a fresh millisecond report plus `REPORT_EXPIRED` still warrants checking the active provider version and opening a Codecov support issue with the commit, upload name, timestamp unit, and processing error.

Codecov documents this temporary escape hatch:

```yaml
codecov:
    max_report_age: off
```

Do not disable age validation before proving the report is fresh. Validate the exact YAML sent to Codecov. Some YAML formatters quote `off`, turning it into a string; where Codecov's live validator accepts it, Boolean `false` avoids that formatter ambiguity:

```yaml
codecov:
    max_report_age: false
```

Keep the workaround narrow and remove it after the provider correctly parses the report timestamp. Age validation protects against accidentally uploading stale reports checked into the repository.

## Inspect Provider Artifacts Safely

When the local CI artifact differs from what Codecov processed, download the raw report through Codecov's current UI or documented interface and compare timestamps and filenames. Some Codecov v1 raw bundles are zstd-compressed and contain multiple named sections; detect the file format before decoding instead of assuming the response is plain XML.

Store downloaded artifacts outside tracked paths, do not execute content from them, and do not expose signed download URLs. Compare only the relevant report section, upload metadata, and generated CI artifact. Then trigger a fresh CI upload after the narrow fix; old errored uploads are historical evidence and do not become successful retroactively.
