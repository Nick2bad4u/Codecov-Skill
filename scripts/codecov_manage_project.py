from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from urllib import error, request

from codecov_manage_api import RequestSpec, api_request, repo_api_endpoint
from codecov_manage_common import CodecovCliError

if TYPE_CHECKING:
    from pathlib import Path

    from codecov_manage_api import CodecovContext

JsonObject = dict[str, Any]

DEFAULT_PAGE_SIZE = 25
VALIDATE_CONFIG_URL = "https://codecov.io/validate"


def context_payload(context: CodecovContext) -> JsonObject:
    return {
        "service": context.service,
        "owner": context.owner,
        "repoName": context.repo_name,
        "repository": f"{context.owner}/{context.repo_name}",
        "repoRoot": str(context.repo_root),
        "baseUrl": context.base_url,
        "tokenEnv": context.token_env_name,
        "codecovYml": str(context.codecov_yml_path) if context.codecov_yml_path else None,
    }


def build_summary(*, context: CodecovContext, branch: str | None, page_size: int) -> JsonObject:
    repo = fetch_repo(context=context)
    branches = fetch_branches(context=context, page_size=page_size)
    commits = fetch_commits(context=context, branch=branch, page_size=page_size)
    flags = fetch_flags(context=context)
    return {
        **context_payload(context),
        "repo": repo,
        "branches": extract_results(branches),
        "commits": extract_results(commits),
        "flags": extract_results(flags),
    }


def fetch_repo(*, context: CodecovContext) -> Any:
    return api_request(
        context=context,
        spec=RequestSpec(method="GET", endpoint=repo_api_endpoint(context)),
    )


def fetch_branches(*, context: CodecovContext, page_size: int) -> Any:
    return api_request(
        context=context,
        spec=RequestSpec(
            method="GET",
            endpoint=repo_api_endpoint(context, "branches/"),
            query={"page_size": str(page_size)},
        ),
    )


def fetch_branch(*, context: CodecovContext, branch: str) -> Any:
    return api_request(
        context=context,
        spec=RequestSpec(method="GET", endpoint=repo_api_endpoint(context, f"branches/{branch}/")),
    )


def fetch_commits(*, context: CodecovContext, branch: str | None, page_size: int) -> Any:
    query = {"page_size": str(page_size)}
    if branch:
        query["branch"] = branch
    return api_request(
        context=context,
        spec=RequestSpec(method="GET", endpoint=repo_api_endpoint(context, "commits/"), query=query),
    )


def fetch_commit(*, context: CodecovContext, commit: str) -> Any:
    return api_request(
        context=context,
        spec=RequestSpec(method="GET", endpoint=repo_api_endpoint(context, f"commits/{commit}/")),
    )


def fetch_commit_report(*, context: CodecovContext, commit: str) -> Any:
    return api_request(
        context=context,
        spec=RequestSpec(method="GET", endpoint=repo_api_endpoint(context, f"commits/{commit}/report/")),
    )


def fetch_report_tree(*, context: CodecovContext, commit: str, path: str | None) -> Any:
    query = {"path": path} if path else None
    return api_request(
        context=context,
        spec=RequestSpec(
            method="GET",
            endpoint=repo_api_endpoint(context, f"commits/{commit}/report/tree/"),
            query=query,
        ),
    )


def fetch_file_report(*, context: CodecovContext, commit: str, path: str) -> Any:
    return api_request(
        context=context,
        spec=RequestSpec(
            method="GET",
            endpoint=repo_api_endpoint(context, f"commits/{commit}/report/file/"),
            query={"path": path},
        ),
    )


def fetch_flags(*, context: CodecovContext) -> Any:
    return api_request(
        context=context,
        spec=RequestSpec(method="GET", endpoint=repo_api_endpoint(context, "flags/")),
    )


def fetch_pulls(*, context: CodecovContext, state: str | None, page_size: int) -> Any:
    query = {"page_size": str(page_size)}
    if state:
        query["state"] = state
    return api_request(
        context=context,
        spec=RequestSpec(method="GET", endpoint=repo_api_endpoint(context, "pulls/"), query=query),
    )


def fetch_pull(*, context: CodecovContext, pull_id: int) -> Any:
    return api_request(
        context=context,
        spec=RequestSpec(method="GET", endpoint=repo_api_endpoint(context, f"pulls/{pull_id}/")),
    )


def compare_commits(*, context: CodecovContext, base: str, head: str) -> Any:
    return api_request(
        context=context,
        spec=RequestSpec(method="GET", endpoint=repo_api_endpoint(context, f"compare/{base}...{head}/")),
    )


def direct_api_call(
    *,
    context: CodecovContext,
    endpoint: str,
    method: str,
    query: dict[str, str],
    form: dict[str, str],
    dry_run: bool,
) -> JsonObject | Any:
    upper_method = method.upper()
    if dry_run:
        return {
            **context_payload(context),
            "dryRun": True,
            "method": upper_method,
            "endpoint": endpoint,
            "query": query,
            "form": form,
        }

    return api_request(
        context=context,
        spec=RequestSpec(
            method=upper_method,
            endpoint=endpoint,
            query=query or None,
            form=form or None,
        ),
    )


def validate_config(*, context: CodecovContext, config_path: Path | None = None) -> JsonObject:
    target_path = config_path or context.codecov_yml_path
    if target_path is None:
        raise CodecovCliError("No codecov.yml file was found. Provide --config or create codecov.yml first.")

    content = target_path.read_text(encoding="utf8")
    request_object = request.Request(  # noqa: S310 - fixed Codecov config validator URL.
        url=VALIDATE_CONFIG_URL,
        data=content.encode("utf8"),
        headers={"Content-Type": "text/yaml"},
        method="POST",
    )

    try:
        with request.urlopen(request_object) as response:  # noqa: S310 - fixed Codecov config validator URL.
            raw_body = response.read().decode("utf8", errors="replace")
    except error.HTTPError as http_error:
        raw_body = http_error.read().decode("utf8", errors="replace")
        return {
            **context_payload(context),
            "configPath": str(target_path),
            "valid": False,
            "status": http_error.code,
            "message": raw_body,
        }
    except error.URLError as url_error:
        raise CodecovCliError(f"Failed to reach Codecov config validator: {url_error.reason}") from url_error

    return {
        **context_payload(context),
        "configPath": str(target_path),
        "valid": True,
        "message": raw_body,
    }


def build_config_template(*, profile: str, flag: str, target: int) -> str:
    ignored_paths = resolve_profile_ignored_paths(profile)
    ignored_block = "\n".join(f"    - {path}" for path in ignored_paths)
    return f"""codecov:
  precision: 2
  range: 75...100
  round: down

coverage:
  status:
    project:
      default:
        target: {target}%
        threshold: 0%
        flags:
          - {flag}
    patch:
      default:
        target: {target}%
        threshold: 0%
        flags:
          - {flag}
  ignore:
{ignored_block}
"""


def resolve_profile_ignored_paths(profile: str) -> tuple[str, ...]:
    normalized = profile.lower()
    if normalized == "python":
        return ("tests/**",)
    if normalized in {"node", "javascript", "typescript"}:
        return ("test/**", "tests/**", "dist/**", "coverage/**")
    return ("coverage/**", "dist/**")


def build_github_action_snippet(
    *,
    flag: str,
    coverage_file: str,
    test_results_file: str | None,
    use_oidc: bool,
) -> str:
    oidc_or_token = "use_oidc: true" if use_oidc else "token: ${{ secrets.CODECOV_TOKEN }}"
    coverage_step = f"""- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v7
  with:
    {oidc_or_token}
    files: {coverage_file}
    flags: {flag}
    name: {flag}-coverage
    report_type: coverage
    fail_ci_if_error: true
    disable_search: true
    verbose: true"""
    if test_results_file is None:
        return coverage_step

    return f"""{coverage_step}

- name: Upload test results to Codecov
  uses: codecov/codecov-action@v7
  with:
    {oidc_or_token}
    files: {test_results_file}
    flags: {flag}
    name: {flag}-test-results
    report_type: test_results
    fail_ci_if_error: true
    disable_search: true
    verbose: true"""


def extract_results(payload: Any) -> list[object]:
    if isinstance(payload, dict):
        payload_object = cast("JsonObject", payload)
        results = payload_object.get("results")
        if isinstance(results, list):
            return cast("list[object]", results)
    return []
